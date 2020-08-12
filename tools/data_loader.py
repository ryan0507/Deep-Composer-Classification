# MIDIDataset


from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

import torch
import numpy as np

from os.path import *
from os import listdir, path


class MIDIDataset(Dataset):
    def __init__(self, split_path, age=False, transform=None):  # start
        self.x_path = []
        self.y = []
        self.transform = transform

        f = open(split_path, "r")
        label = -1  # init
        for line in f:
            # find composer num
            temp = line.split("/")
            for element in temp:
                if "composer" in element:
                    label = int(element.replace("composer", ""))  # composer num (0-12)
                    if age:  # age == True
                        if label in [2, 6]:
                            label = 0  # Baroque
                        elif label in [4, 8, 9, 12]:
                            label = 1  # Classical
                        else:
                            label = 2  # Romanticism

                    break

            self.x_path.append(line.replace("\n", ""))
            self.y.append(label)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):  # supports retrieving each file
        # Actually fetch the data
        X = np.load(self.x_path[idx], allow_pickle=True)
        Y = self.y[idx]
        # F = self.x_path[idx].replace(self.path, "")
        # print(F)

        data = {"X": X, "Y": Y}
        if self.transform:
            data = self.transform(data)
        # return (
        #     torch.tensor(X, dtype=torch.float32),
        #     torch.tensor(Y, dtype=torch.long),
        # )
        return data


# @ TEST
# MyDataset = MIDIDataset('test')
# MyDataLoader = DataLoader(MyDataset, batch_size=10, shuffle=True)
# print(len(MyDataLoader))
# for data in MyDataLoader:
# 	print(len(data[0]))
# 	break
