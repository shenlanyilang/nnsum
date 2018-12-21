import pathlib

from .module_cli_parser import ModuleCLIParser
import nnsum.embedding_context as ec
import nnsum.seq2seq as s2s
import nnsum.seq2clf as s2c
import nnsum.optimizer as opt


def seq2seq():
    parser = ModuleCLIParser("Train a sequence-to-sequence model.")
    parser.add_argument("--train-source", type=pathlib.Path, required=True,
                        help="Path to training source file or directory")
    parser.add_argument("--train-target", type=pathlib.Path, required=True,
                        help="Path to training target file or directory")
    parser.add_argument("--valid-source", type=pathlib.Path, required=True,
                        help="Path to validation source file or directory")
    parser.add_argument("--valid-target", type=pathlib.Path, required=True,
                        help="Path to validation target file or directory")
    parser.add_argument("--gpu", type=int, default=-1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model-path", type=pathlib.Path, required=False)
    parser.add_argument("--epochs", default=50, type=int)
    parser.add_module_cli("src-emb", ec.cli.new_parser())
    parser.add_module_cli("tgt-emb", ec.cli.new_parser())
    parser.add_module_cli("enc", s2s.cli.new_rnn_encoder_parser())
    parser.add_module_cli("dec", s2s.cli.new_rnn_decoder_parser())
    parser.add_module_cli("opt", opt.cli.new_optimizer_parser())
    parser.add_module_cli("sch", opt.cli.new_lr_scheduler_parser())

    return parser


def cnn_seq2clf():
    parser = ModuleCLIParser("Train a CNN sequence-to-classification model.")
    parser.add_argument("--train-source", type=pathlib.Path, required=True,
                        help="Path to training source file or directory")
    parser.add_argument("--train-target", type=pathlib.Path, required=True,
                        help="Path to training target file or directory")
    parser.add_argument("--valid-source", type=pathlib.Path, required=True,
                        help="Path to validation source file or directory")
    parser.add_argument("--valid-target", type=pathlib.Path, required=True,
                        help="Path to validation target file or directory")
    parser.add_argument("--gpu", type=int, default=-1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model-path", type=pathlib.Path, required=False)
    parser.add_argument("--source-vocab", type=pathlib.Path, required=False)
    parser.add_argument("--balance-weights", action="store_true", 
                        default=False)
    parser.add_argument("--epochs", default=50, type=int)
    parser.add_module_cli("opt", opt.cli.new_optimizer_parser())
    parser.add_module_cli("sch", opt.cli.new_lr_scheduler_parser())
    parser.add_module_cli("emb", ec.cli.new_parser())
    parser.add_module_cli("enc", s2c.cli.new_cnn_encoder_parser())
    parser.add_module_cli("lbl", ec.cli.new_label_context_parser())

    return parser

def seq2clf():
    parser = ModuleCLIParser("Train a sequence-to-classification model.")
    parser.add_argument("--train-source", type=pathlib.Path, required=True,
                        help="Path to training source file or directory")
    parser.add_argument("--train-target", type=pathlib.Path, required=True,
                        help="Path to training target file or directory")
    parser.add_argument("--valid-source", type=pathlib.Path, required=True,
                        help="Path to validation source file or directory")
    parser.add_argument("--valid-target", type=pathlib.Path, required=True,
                        help="Path to validation target file or directory")
    parser.add_argument("--gpu", type=int, default=-1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model-path", type=pathlib.Path, required=False)
    parser.add_argument("--max-entropy-for-missing-data", '-M', 
                        action='store_true')
    parser.add_argument("--min-attention-entropy", '-A', 
                        action='store_true')
    parser.add_argument("--use-njsd-loss", '-N', 
                        action='store_true')
    parser.add_argument("--source-vocab", type=pathlib.Path, required=False)

    parser.add_module_cli("emb", ec.cli.new_parser())
    parser.add_module_cli("lbl", ec.cli.new_parser())

    return parser
