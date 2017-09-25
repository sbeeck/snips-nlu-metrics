from __future__ import unicode_literals

import io
import json

from nlu_metrics.utils.dataset_utils import (get_stratified_utterances)
from nlu_metrics.utils.metrics_utils import (create_k_fold_batches,
                                             compute_engine_metrics,
                                             aggregate_metrics,
                                             compute_precision_recall)
from nlu_metrics.utils.nlu_engine_utils import get_inference_engine, \
    get_trained_engine
from nlu_metrics.utils.constants import INTENTS, UTTERANCES


def compute_cross_val_metrics(
        dataset,
        training_engine_class,
        inference_engine_class,
        nb_folds=5,
        training_utterances=None):
    """Compute the main NLU metrics on the dataset using cross validation

    :param dataset: dict or str, dataset or path to dataset
    :param training_engine_class: python class to use for training
    :param inference_engine_class: python class to use for inference
    :param nb_folds: int, number of folds to use for cross validation
    :param training_utterances: int, max number of utterances to use for
        training
    :return: dict containing the metrics

    """

    metrics_config = {
        "nb_folds": nb_folds,
        "training_utterances": training_utterances
    }

    if isinstance(dataset, (str, unicode)):
        with io.open(dataset, encoding="utf8") as f:
            dataset = json.load(f)

    nb_utterances = {intent: len(data[UTTERANCES])
                     for intent, data in dataset[INTENTS].iteritems()}
    total_utterances = sum(nb_utterances.values())
    should_skip = total_utterances < nb_folds or (
        training_utterances is not None and
        total_utterances < training_utterances)
    if should_skip:
        print("Skipping group because number of utterances is too "
              "low (%s)" % total_utterances)
        return {
            "config": metrics_config,
            "training_info": "not enough utterances for training (%s)"
                             % total_utterances,
            "metrics": None
        }
    batches = create_k_fold_batches(dataset, nb_folds, training_utterances)
    global_metrics = dict()

    for batch_index, (train_dataset, test_utterances) in enumerate(batches):
        try:
            language = train_dataset["language"]
            trained_engine = get_trained_engine(train_dataset,
                                                training_engine_class)
            inference_engine = get_inference_engine(language,
                                                    trained_engine.to_dict(),
                                                    inference_engine_class)
        except Exception as e:
            print("Skipping group because of training error: %s" % e.message)
            return {
                "config": metrics_config,
                "training_info": "training error: '%s'" % e.message,
                "metrics": None
            }
        batch_metrics = compute_engine_metrics(inference_engine,
                                               test_utterances)
        global_metrics = aggregate_metrics(global_metrics, batch_metrics)

    global_metrics = compute_precision_recall(global_metrics)

    for intent, metrics in global_metrics.iteritems():
        metrics["intent_utterances"] = nb_utterances.get(intent, 0)

    return {
        "config": metrics_config,
        "metrics": global_metrics
    }


def compute_train_test_metrics(
        train_dataset,
        test_dataset,
        training_engine_class,
        inference_engine_class,
        verbose=False):
    """Compute the main NLU metrics on `test_dataset` after having trained on
    `train_dataset`

    :param train_dataset: dict or str, dataset or path to dataset used for
        training
    :param test_dataset: dict or str, dataset or path to dataset used for
        testing
    :param training_engine_class: python class to use for training
    :param inference_engine_class: python class to use for inference
    :param training_engine_class: SnipsNLUEngine class, if `None` then the
        engine used for training is created with the specified
        `snips_nlu_version`
    :param verbose: if `True` it will print prediction errors
    :return: dict containing the metrics
    """
    if isinstance(train_dataset, (str, unicode)):
        with io.open(train_dataset, encoding="utf8") as f:
            train_dataset = json.load(f)

    if isinstance(test_dataset, (str, unicode)):
        with io.open(test_dataset, encoding="utf8") as f:
            test_dataset = json.load(f)

    language = train_dataset["language"]
    trained_engine = get_trained_engine(train_dataset, training_engine_class)
    inference_engine = get_inference_engine(language, trained_engine.to_dict(),
                                            inference_engine_class)
    utterances = get_stratified_utterances(test_dataset, seed=None,
                                           shuffle=False)
    metrics = compute_engine_metrics(inference_engine, utterances, verbose)
    metrics = compute_precision_recall(metrics)
    return {"metrics": metrics}
