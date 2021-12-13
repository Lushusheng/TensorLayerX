#! /usr/bin/python
# -*- coding: utf-8 -*-
# The tensorlayer and tensorflow operators can be mixed
import os
os.environ['TL_BACKEND'] = 'paddle'

import time
import paddle as pd
from tensorlayer.layers import Module
import tensorlayer as tl
from tensorlayer.dataflow import Dataset, Dataloader
from tensorlayer.layers import (Conv2d, Dense, Flatten, MaxPool2d, BatchNorm2d)
from tensorlayer.vision.transforms import (Compose, Resize, RandomFlipHorizontal, RandomContrast, RandomBrightness, StandardizePerImage, RandomCrop)
# enable debug logging
tl.logging.set_verbosity(tl.logging.DEBUG)

# prepare cifar10 data
X_train, y_train, X_test, y_test = tl.files.load_cifar10_dataset(shape=(-1, 32, 32, 3), plotable=False)


class CNN(Module):

    def __init__(self):
        super(CNN, self).__init__()
        # weights init
        W_init = tl.initializers.truncated_normal(stddev=5e-2)
        W_init2 = tl.initializers.truncated_normal(stddev=0.04)
        b_init2 = tl.initializers.constant(value=0.1)

        self.conv1 = Conv2d(64, (5, 5), (1, 1), padding='SAME', W_init=W_init, b_init=None, name='conv1', in_channels=3)
        self.bn1 = BatchNorm2d(num_features=64, act=tl.ReLU)
        self.maxpool1 = MaxPool2d((3, 3), (2, 2), padding='SAME', name='pool1')

        self.conv2 = Conv2d(
            64, (5, 5), (1, 1), padding='SAME', W_init=W_init, b_init=None, name='conv2', in_channels=64
        )
        self.bn2 = BatchNorm2d(num_features=64, act=tl.ReLU)
        self.maxpool2 = MaxPool2d((3, 3), (2, 2), padding='SAME', name='pool2')

        self.flatten = Flatten(name='flatten')
        self.dense1 = Dense(384, act=tl.ReLU, W_init=W_init2, b_init=b_init2, name='dense1relu', in_channels=2304)
        self.dense2 = Dense(192, act=tl.ReLU, W_init=W_init2, b_init=b_init2, name='dense2relu', in_channels=384)
        self.dense3 = Dense(10, act=None, W_init=W_init2, name='output', in_channels=192)

    def forward(self, x):
        z = self.conv1(x)
        z = self.bn1(z)
        z = self.maxpool1(z)
        z = self.conv2(z)
        z = self.bn2(z)
        z = self.maxpool2(z)
        z = self.flatten(z)
        z = self.dense1(z)
        z = self.dense2(z)
        z = self.dense3(z)
        return z

# get the network
net = CNN()

# training settings
batch_size = 128
n_epoch = 500
learning_rate = 0.0001
print_freq = 5
shuffle_buffer_size = 128
metrics = tl.metric.Accuracy()

train_weights = net.trainable_weights
optimizer = tl.optimizers.Adam(learning_rate)
# looking for decay learning rate? see https://github.com/tensorlayer/srgan/blob/master/train.py

class make_dataset(Dataset):

    def __init__(self, data, label, transforms):
        self.data = data
        self.label = label
        self.transforms = transforms

    def __getitem__(self, idx):
        x = self.data[idx].astype('uint8')
        y = self.label[idx].astype('int64')
        x = self.transforms(x)

        return x, y

    def __len__(self):

        return len(self.label)

train_transforms = Compose([
    RandomCrop(size=[24,24]),
    RandomFlipHorizontal(),
    RandomBrightness(brightness_factor=(0.5, 1.5)),
    RandomContrast(contrast_factor=(0.5, 1.5)),
    StandardizePerImage()
])

test_transforms = Compose([
    Resize(size=(24,24)),
    StandardizePerImage()
])

train_dataset = make_dataset(data=X_train, label=y_train, transforms=train_transforms)
test_dataset = make_dataset(data=X_test, label=y_test, transforms=test_transforms)

train_dataset = tl.dataflow.FromGenerator(train_dataset,output_types=(tl.float32, tl.int64))
test_dataset = tl.dataflow.FromGenerator(test_dataset,output_types=(tl.float32, tl.int64))

train_dataset = Dataloader(train_dataset, batch_size=batch_size, shuffle=True, shuffle_buffer_size=128)
test_dataset = Dataloader(test_dataset, batch_size=batch_size)

for epoch in range(n_epoch):
    train_loss, train_acc, n_iter = 0, 0, 0
    start_time = time.time()
    for X_batch, y_batch in train_dataset:
        net.set_train()
        output = net(X_batch)
        loss = pd.nn.functional.cross_entropy(output, y_batch)
        loss_ce = loss.numpy()
        grads = optimizer.gradient(loss, train_weights)
        optimizer.apply_gradients(zip(grads, train_weights))

        train_loss += loss_ce

        if metrics:
            metrics.update(output, y_batch)
            train_acc += metrics.result()
            metrics.reset()
        n_iter += 1

        print("Epoch {} of {} took {}".format(epoch + 1, n_epoch, time.time() - start_time))
        print("   train loss: {}".format(train_loss / n_iter))
        print("   train acc:  {}".format(train_acc / n_iter))