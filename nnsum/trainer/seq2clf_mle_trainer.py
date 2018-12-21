import torch
import torch.nn.functional as F
import numpy as np

from ignite.engine import Engine, Events
from ignite._utils import _to_hours_mins_secs
from ignite.handlers import ModelCheckpoint

from nnsum.metrics import Loss, ClassificationMetrics
from nnsum.sequence_cross_entropy import sequence_cross_entropy
from nnsum.loss import binary_entropy
import nnsum.loss

from colorama import Fore, Style
import ujson as json

import time
from collections import OrderedDict


def seq2clf_mle_trainer(model, optimizer_scheduler, train_dataloader,
                        validation_dataloader, max_epochs=10,
                        grad_clip=5, gpu=-1, model_path=None,
                        results_path=None, label_weights=None):

    trainer = create_trainer(
        model, optimizer_scheduler, grad_clip=grad_clip, gpu=gpu,
        label_weights=label_weights)
    evaluator = create_evaluator(
        model, validation_dataloader, gpu=gpu)

    xentropy = Loss(
        output_transform=lambda o: (o["total_xent"], o["total_tokens"]))
    xentropy.attach(trainer, "x-entropy")
    xentropy.attach(evaluator, "x-entropy")

    clf_metrics = OrderedDict()
    def getter(name):
        def f(out):
            return (out["labels"][name]["true"], out["labels"][name]["pred"])
        return f
    for name, vocab in model.target_embedding_context.named_vocabs.items():
        clf_metrics[name] = ClassificationMetrics(
            vocab, output_transform=getter(name))
        clf_metrics[name].attach(evaluator, name)

    @trainer.on(Events.STARTED)
    def init_history(trainer):
        trainer.state.training_history = {"x-entropy": []}
        trainer.state.validation_history = {"x-entropy": [], 
                                            "accuracy": [],
                                            "f1": []}
        trainer.state.min_valid_xent = float("inf")
        trainer.state.max_valid_acc = float("-inf")
        trainer.state.max_valid_f1 = float("-inf")

    @trainer.on(Events.EPOCH_STARTED)
    def log_epoch_start_time(trainer):
        trainer.state.start_time = time.time()

    @trainer.on(Events.ITERATION_COMPLETED)
    def log_training_loss(trainer):

        xent = xentropy.compute()
        iterate = trainer.state.iteration
        msg = "Epoch[{}] Training {} / {}  X-Entropy: {:.3f}".format(
            trainer.state.epoch, iterate, len(train_dataloader),
            xent)

        if iterate < len(train_dataloader):
            print(msg, end="\r", flush=True)
        else:
            print(" " * len(msg), end="\r", flush=True)

    @evaluator.on(Events.ITERATION_COMPLETED)
    def log_validation_loss(evaluator):

        xent = xentropy.compute()
        iterate = evaluator.state.iteration
        msg = "Epoch[{}] Validating {} / {}  X-Entropy: {:.3f}".format(
            trainer.state.epoch, iterate, len(validation_dataloader),
            xent)
        if iterate < len(validation_dataloader):
            print(msg, end="\r", flush=True)
        else:
            print(" " * len(msg), end="\r", flush=True)

    @trainer.on(Events.EPOCH_COMPLETED)
    def log_validation_results(trainer):
        trainer.state.iteration = 0
        train_metrics = trainer.state.metrics
        print("Epoch[{}] Training X-Entropy={:.3f}".format(
            trainer.state.epoch, train_metrics["x-entropy"]))
        trainer.state.training_history["x-entropy"].append(
            train_metrics["x-entropy"])

        evaluator.run(validation_dataloader)
        metrics = evaluator.state.metrics
        
        valid_metrics = evaluator.state.metrics
        valid_history = trainer.state.validation_history
        valid_metric_strings = []

        if valid_metrics["x-entropy"] < trainer.state.min_valid_xent:
            valid_metric_strings.append(
                Fore.GREEN + \
                "X-Entropy={:.3f}".format(valid_metrics["x-entropy"]) + \
                Style.RESET_ALL)
            trainer.state.min_valid_xent = valid_metrics["x-entropy"]
        else:
            valid_metric_strings.append(
                "X-Entropy={:.3f}".format(valid_metrics["x-entropy"]))

        valid_clf_metric_strings = ["F1  "]
        avg_f1 = 0
        for name in clf_metrics:
            valid_clf_metric_strings.append(
                "{}: {:0.3f} ".format(
                    name,
                    valid_metrics[name]["f-measure"]["macro avg."]))
            avg_f1 += valid_metrics[name]["f-measure"]["macro avg."]
        avg_f1 = avg_f1 / len(clf_metrics)
        if avg_f1 > trainer.state.max_valid_f1:
            trainer.state.max_valid_f1 = avg_f1
            valid_clf_metric_strings.insert(
                0, 
                Fore.GREEN + "AVG: {:0.3f}".format(avg_f1) + Style.RESET_ALL)
        else:
            valid_clf_metric_strings.insert(0, "AVG: {:0.3f}".format(avg_f1))
           
        print("Epoch[{}] Validation {}".format(
            trainer.state.epoch,
            " ".join(valid_metric_strings))) 
        print(" ".join(valid_clf_metric_strings))

        valid_clf_metric_strings = ["ACC "]
        avg_acc = 0
        for name in clf_metrics:
            valid_clf_metric_strings.append(
                "{}: {:0.3f} ".format(
                    name,
                    valid_metrics[name]["accuracy"]))
            avg_acc += valid_metrics[name]["accuracy"]
        avg_acc = avg_acc / len(clf_metrics)
        if avg_acc > trainer.state.max_valid_acc:
            trainer.state.max_valid_acc = avg_acc
            valid_clf_metric_strings.insert(
                0, 
                Fore.GREEN + "AVG: {:0.3f}".format(avg_acc) + Style.RESET_ALL)
        else:
            valid_clf_metric_strings.insert(
                0, "AVG: {:0.3f}".format(avg_acc))
        print(" ".join(valid_clf_metric_strings))
 
        valid_history["x-entropy"].append(valid_metrics["x-entropy"])
        valid_history["accuracy"].append(avg_acc)
        valid_history["f1"].append(avg_f1)
        optimizer_scheduler.step(
            valid_history[optimizer_scheduler.metric][-1])
        #valid_history["rouge-1"].append(valid_metrics["rouge"]["rouge-1"])
        #valid_history["rouge-2"].append(valid_metrics["rouge"]["rouge-2"])

        hrs, mins, secs = _to_hours_mins_secs(
            time.time() - trainer.state.start_time)
        print("Epoch[{}] Time Taken: {:02.0f}:{:02.0f}:{:02.0f}".format(
            trainer.state.epoch, hrs, mins, secs))

        print()

        if results_path:
            if not results_path.parent.exists():
                results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.write_text(
                json.dumps({"training": trainer.state.training_history,
                            "validation": trainer.state.validation_history}))

    if model_path:
        checkpoint = create_checkpoint(
            model_path, metric_name=optimizer_scheduler.metric)
        trainer.add_event_handler(
            Events.EPOCH_COMPLETED, checkpoint, {"model": model})

    trainer.run(train_dataloader, max_epochs=max_epochs)

def create_trainer(model, optimizer_scheduler, grad_clip=5, gpu=-1, 
                   label_weights=None):

    def _update(engine, batch):
        if gpu > -1: 
            _seq2clf2gpu(batch, gpu)
        model.train()
        optimizer_scheduler.optimizer.zero_grad()

        logits = model(batch)

        total_xents = 0
        total_nents = 0

        for cls, cls_logits in logits.items():
            if label_weights is not None:
                weight = label_weights[cls]
            else:
                weight = None

            cls_avg_xent = F.cross_entropy(cls_logits, batch["targets"][cls],
                                           weight=weight)
            total_xents = total_xents + cls_avg_xent

        obj = total_xents / len(logits)

        obj.backward()
          
        for v in logits.values():
            batch_size = v.size(0)
            break
        
        for param in model.parameters():
            param.grad.data.clamp_(-grad_clip, grad_clip)
        optimizer_scheduler.optimizer.step()

        result = {"total_xent": total_xents,
                  "total_tokens": batch_size}
        return result

    trainer = Engine(_update)
   
    return trainer

def create_evaluator(model, dataloader, gpu=-1, min_attention_entropy=False,
                     max_entropy_for_missing_data=False, use_njsd_loss=False):

    pad_index = -1

    def _evaluator(engine, batch):

        if gpu > -1: 
            _seq2clf2gpu(batch, gpu)

        model.eval()

        with torch.no_grad():

            logits = model(batch)
            total_xents = 0

            output_labels = {}
            output_entropy = {}
            for cls, cls_logits in logits.items():
               
                cls_avg_xent = F.cross_entropy(
                    cls_logits, batch["targets"][cls], ignore_index=pad_index)
                total_xents = total_xents + cls_avg_xent
                output_labels[cls] = {
                    "pred": cls_logits.max(1)[1].cpu(),
                    "true": batch["targets"][cls].cpu()}

            for v in logits.values():
                batch_size = v.size(0)
                break

            result = {"total_xent": total_xents, 
                      "total_tokens": batch_size,
                      "labels": output_labels}

            return result 
    return Engine(_evaluator)

def create_checkpoint(model_path, metric_name="x-entropy"):

    dirname = str(model_path.parent)
    prefix = str(model_path.name)

    def _score_func(trainer):
        model_idx = trainer.state.epoch - 1

        val = trainer.state.validation_history[metric_name][model_idx]
        if metric_name == "x-entropy":
            val = -val
        return val

    checkpoint = ModelCheckpoint(dirname, prefix, score_function=_score_func,
                                 require_empty=False, score_name=metric_name)
    return checkpoint

def _seq2clf2gpu(batch, gpu):
    sf = batch["source_features"]
    for feat in sf:
        sf[feat] = sf[feat].cuda(gpu)
    batch["source_lengths"] = batch["source_lengths"].cuda(gpu)
    for feat in batch["targets"]:
        batch["targets"][feat] = batch["targets"][feat].cuda(gpu)
    batch["source_mask"] = batch["source_mask"].cuda(gpu)