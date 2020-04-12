from __future__ import print_function

import datetime
import sys

import numpy
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import tqdm
from sklearn.metrics import precision_score, f1_score, recall_score, accuracy_score
from torch.utils import data

from dataset import FunctionIdentificationDataset

torch.manual_seed(1)


kernel_size = 20


class CNNTagger(nn.Module):
    def __init__(self, embedding_dim, kernel_size, hidden_dim, vocab_size, tagset_size):
        super(CNNTagger, self).__init__()
        self._kernel_size = kernel_size

        self.hidden_dim = hidden_dim

        self.word_embeddings = nn.Embedding(vocab_size, embedding_dim)

        self.conv = nn.Conv2d(1, hidden_dim, kernel_size=(kernel_size, embedding_dim))

        self.hidden2tag = nn.Linear(hidden_dim, tagset_size)

    def forward(self, sample):
        embeds = self.word_embeddings(sample)
        conv_in = embeds.view(1, 1, len(sample), -1)
        conv_out = self.conv(conv_in)
        conv_out = F.relu(conv_out)
        hidden_in = conv_out.view(self.hidden_dim, len(sample) + 1 - self._kernel_size).transpose(0, 1)
        tag_space = self.hidden2tag(hidden_in)
        tag_scores = F.log_softmax(tag_space, dim=1)

        return tag_scores


def main():
    dataset = FunctionIdentificationDataset(sys.argv[1], block_size=1000, padding_size=kernel_size - 1)

    train_size = int(len(dataset) * 0.9)
    test_size = len(dataset) - train_size
    train_dataset, test_dataset = data.random_split(dataset, [train_size, test_size])

    model = CNNTagger(embedding_dim=64, vocab_size=258, hidden_dim=16,  tagset_size=2, kernel_size=kernel_size)

    loss_function = nn.NLLLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    best_accuracy = 0
    best_pr = 0
    best_recall = 0
    best_f1 = 0

    train_loader = data.DataLoader(train_dataset, shuffle=True)
    test_loader = data.DataLoader(test_dataset)

    current_time = datetime.datetime.now()
    print("start time", current_time)
    try:
        for sample_number, (sample, tags) in tqdm.tqdm(enumerate(train_loader), total=len(train_loader)):
            sample = sample[0]
            tags = tags[0]
            model.zero_grad()

            tag_scores = model(sample)

            loss = loss_function(tag_scores, tags)
            loss.backward()
            optimizer.step()

            if sample_number % 10000 == 0:
                model.eval()
                # for loader, name in ((test_loader, "test"), (train_loader, "train")):
                for loader, name in ((test_loader, "test"),):
                    with torch.no_grad():
                        all_tags = []
                        all_tag_scores = []
                        for sample, tags in tqdm.tqdm(loader, total=len(loader)):
                            model.zero_grad()

                            sample = sample[0]
                            tags = tags[0]

                            tag_scores = model(sample)

                            all_tags.extend(tags.numpy())
                            all_tag_scores.extend(tag_scores.numpy())

                        all_tags = numpy.array(all_tags)
                        all_tag_scores = numpy.array(all_tag_scores).argmax(axis=1)
                        accuracy = accuracy_score(all_tags, all_tag_scores)
                        pr = precision_score(all_tags, all_tag_scores)
                        recall = recall_score(all_tags, all_tag_scores)
                        f1 = f1_score(all_tags, all_tag_scores)
                        if name == "test":
                            if f1 > best_f1:
                                best_accuracy = accuracy
                                best_pr = pr
                                best_recall = recall
                                best_f1 = f1
                        print("name: {}".format(name))
                        print("accuracy: {}".format(accuracy))
                        print("pr: {}".format(pr))
                        print("recall: {}".format(recall))
                        print("f1: {}".format(f1))
                model.train()

    except KeyboardInterrupt:
        pass
    print("best_accuracy: {}".format(best_accuracy))
    print("best_pr: {}".format(best_pr))
    print("best_recall: {}".format(best_recall))
    print("best_f1: {}".format(best_f1))


if __name__ == '__main__':
    main()