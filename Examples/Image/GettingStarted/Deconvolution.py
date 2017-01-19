# Copyright (c) Microsoft. All rights reserved.

# Licensed under the MIT license. See LICENSE.md file in the project root
# for full license information.
# ==============================================================================

from __future__ import print_function
import numpy as np
import sys
import os
import cntk

# Paths relative to current python file.
abs_path   = os.path.dirname(os.path.abspath(__file__))
data_path  = os.path.join(abs_path, "..", "DataSets", "MNIST")
model_path = os.path.join(abs_path, "Output", "Models")

# Define the reader for both training and evaluation action.
def create_reader(path, is_training, input_dim, label_dim):
    return cntk.io.MinibatchSource(cntk.io.CTFDeserializer(path, cntk.io.StreamDefs(
        features  = cntk.io.StreamDef(field='features', shape=input_dim),
        labels    = cntk.io.StreamDef(field='labels',   shape=label_dim)
    )), randomize=is_training, epoch_size = cntk.io.INFINITELY_REPEAT if is_training else cntk.io.FULL_DATA_SWEEP)


# Creates and trains a feedforward classification model for MNIST images
def convnet_mnist(debug_output=False):
    image_height = 28
    image_width  = 28
    num_channels = 1
    input_dim = image_height * image_width * num_channels
    num_output_classes = 10

    # Input variables denoting the features and label data
    input_var = cntk.ops.input_variable((num_channels, image_height, image_width), np.float32)
    #label_var = cntk.ops.input_variable(num_output_classes, np.float32)

    # Instantiate the feedforward classification model
    scaled_input = cntk.ops.element_times(cntk.ops.constant(0.00390625), input_var)

    with cntk.layers.default_options(activation=cntk.ops.relu, pad=False): 
        conv1 = cntk.layers.Convolution((5,5), 1, pad=True)(scaled_input)
        pool1 = cntk.layers.MaxPooling((4,4), (4,4))(conv1)
        z     = cntk.layers.MaxUnpooling((4,4), (4,4))(pool1, conv1)

    # err = cntk.ops.minus(z, scaled_input)
    f2 = cntk.ops.element_times(cntk.ops.constant(0.00390625), input_var)
    err = cntk.ops.reshape(cntk.ops.minus(z, f2), (784))
    sq_err = cntk.ops.element_times(err, err)
    mse = cntk.ops.reduce_mean(sq_err)
    rmse_loss = cntk.ops.sqrt(mse)
    rmse_eval = cntk.ops.sqrt(mse)

    reader_train = create_reader(os.path.join(data_path, 'Train-28x28_cntk_text.txt'), True, input_dim, num_output_classes)

    # training config
    epoch_size = 60000                    # for now we manually specify epoch size
    minibatch_size = 64

    # Set learning parameters
    lr_per_sample    = [0.00015]
    lr_schedule      = cntk.learning_rate_schedule(lr_per_sample, cntk.learner.UnitType.sample, epoch_size)
    mm_time_constant = [600]
    mm_schedule      = cntk.learner.momentum_as_time_constant_schedule(mm_time_constant, epoch_size)

    # Instantiate the trainer object to drive the model training
    learner = cntk.learner.momentum_sgd(z.parameters, lr_schedule, mm_schedule, unit_gain=True)
    trainer = cntk.Trainer(z, rmse_loss, rmse_eval, learner)

    # define mapping from reader streams to network inputs
    input_map = {
        input_var : reader_train.streams.features,
        #label_var : reader_train.streams.labels
    }

    cntk.utils.log_number_of_parameters(z) ; print()
    progress_printer = cntk.utils.ProgressPrinter(tag='Training')

    # Get minibatches of images to train with and perform model training
    max_epochs = 3
    for epoch in range(max_epochs):       # loop over epochs
        sample_count = 0
        while sample_count < epoch_size:  # loop over minibatches in the epoch
            data = reader_train.next_minibatch(min(minibatch_size, epoch_size - sample_count), input_map=input_map) # fetch minibatch.
            trainer.train_minibatch(data)                                   # update model with it
            sample_count += data[input_var].num_samples                     # count samples processed so far
            progress_printer.update_with_trainer(trainer, with_metric=True) # log progress

        progress_printer.epoch_summary(with_metric=True)
        z.save_model(os.path.join(model_path, "Deconv_py_{}.dnn".format(epoch)))
    
    # Load test data
    reader_test = create_reader(os.path.join(data_path, 'Test-28x28_cntk_text.txt'), False, input_dim, num_output_classes)

    input_map = {
        input_var : reader_test.streams.features,
        #label_var : reader_test.streams.labels
    }

    # Test data for trained model
    epoch_size = 10000
    minibatch_size = 1024

    # process minibatches and evaluate the model
    metric_numer    = 0
    metric_denom    = 0
    sample_count    = 0
    minibatch_index = 0

    while sample_count < epoch_size:
        current_minibatch = min(minibatch_size, epoch_size - sample_count)

        # Fetch next test min batch.
        data = reader_test.next_minibatch(current_minibatch, input_map=input_map)

        # minibatch data to be trained with
        metric_numer += trainer.test_minibatch(data) * current_minibatch
        metric_denom += current_minibatch

        # Keep track of the number of samples processed so far.
        sample_count += data[input_var].num_samples
        minibatch_index += 1

    print("")
    print("Final Results: Minibatch[1-{}]: errs = {:0.2f}% * {}".format(minibatch_index+1, (metric_numer*100.0)/metric_denom, metric_denom))
    print("")

    return metric_numer/metric_denom

if __name__=='__main__':
    convnet_mnist()
