import torch


class CopyDataset(object):
    def __init__(self, vocab_size, max_length, dataset_size, random_seed=None):
        self._max_length = max_length
        self._vocab_size = vocab_size
        self._dataset_size = dataset_size

        if random_seed is not None:
            torch.manual_seed(random_seed)
        
        self._random_seeds = torch.LongTensor(dataset_size).random_(0, 2**31)
        self._probs = torch.FloatTensor(vocab_size).fill_(1 / vocab_size)

    def seed(self, random_seed):
        torch.manual_seed(random_seed)
        self._random_seeds = torch.LongTensor(len(self)).random_(0, 2**31)

    def word_list(self):
        return [str(idx) for idx in range(self._vocab_size)]

    def __len__(self):
        return self._dataset_size

    def __getitem__(self, index):
        
        torch.manual_seed(self._random_seeds[index])
        length = torch.LongTensor(1).random_(1, self._max_length + 1).item()

        indices = torch.multinomial(self._probs, length, replacement=False)
        tokens = [str(idx) for idx in indices.tolist()]
        return {"source": {"tokens": tokens}, "target": {"tokens": tokens}}