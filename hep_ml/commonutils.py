"""
`commonutils` contains some helpful functions and classes
which are often used (by other modules)
"""

from __future__ import print_function, division, absolute_import

import math
import io
import numbers
import numpy
import pandas
from numpy.random.mtrand import RandomState
from scipy.special import expit
import sklearn.cross_validation
from sklearn.utils.validation import check_arrays
#from sklearn.neighbors.unsupervised import NearestNeighbors
from sklearn.neighbors import NearestNeighbors

__author__ = "Alex Rogozhnikov"


def execute_notebook(filename):
    """Allows one to execute cell-by-cell some IPython notebook provided its name"""
    from IPython.core.getipython import get_ipython
    from IPython.nbformat import current

    with io.open(filename) as f:
        notebook = current.read(f, 'json')
    ip = get_ipython()
    for cell in notebook.worksheets[0].cells:
        if cell.cell_type == 'code':
            ip.run_cell(cell.input)


def map_on_cluster(ipc_profile, *args, **kw_args):
    """The same as map, but the first argument is ipc_profile. Distributes the task over IPython cluster.
    Important: this function is not lazy!
    :param str|None ipc_profile: the IPython cluster profile to use.
    :return: the result of mapping
    """
    if ipc_profile is None:
        return list(map(*args, **kw_args))
    else:
        from IPython.parallel import Client

        return Client(profile=ipc_profile).load_balanced_view().map_sync(*args, **kw_args)


def sigmoid_function(x, width):
    """ Sigmoid function is smoothing of Heaviside function,
    the less width, the closer we are to Heaviside function
    :type x: array-like with floats, arbitrary shape
    :type width: float, if width == 0, this is simply Heaviside function
    """
    assert width >= 0, 'the width should be non-negative'
    if abs(width) > 0.0001:
        return expit(x / width)
    else:
        return (x > 0) * 1.0


def generate_sample(n_samples, n_features, distance=2.0):
    """Generates some test distribution,
    signal and background distributions are gaussian with same dispersion and different centers,
    all variables are independent (gaussian correlation matrix is identity)"""
    from sklearn.datasets import make_blobs

    centers = numpy.zeros((2, n_features))
    centers[0, :] = - distance / 2
    centers[1, :] = distance / 2

    X, y = make_blobs(n_samples=n_samples, n_features=n_features, centers=centers)
    columns = ["column" + str(x) for x in range(n_features)]
    X = pandas.DataFrame(X, columns=columns)
    return X, y


def check_uniform_label(uniform_label):
    """ Convert to numpy.array
    :param uniform_label: label or list of labels (examples: 0, 1, [0], [1], [0, 1])
    :return: numpy.array (with [0], [1] or [0, 1])
    """
    if isinstance(uniform_label, numbers.Number):
        return numpy.array([uniform_label])
    else:
        return numpy.array(uniform_label)


def reorder_by_first(*arrays):
    """ Applies the same permutation to all passed arrays,
    permutation sorts the first passed array """
    arrays = check_arrays(*arrays)
    order = numpy.argsort(arrays[0])
    return [arr[order] for arr in arrays]


def reorder_by_first_inverse(*arrays):
    """The same as reorder, but the first array is ordered by descending"""
    arrays = check_arrays(*arrays)
    order = numpy.argsort(-arrays[0])
    return [arr[order] for arr in arrays]


def train_test_split(*arrays, **kw_args):
    """Does the same thing as train_test_split, but preserves columns in DataFrames.
    Uses the same parameters: test_size, train_size, random_state, and has the same interface
    :type list[numpy.array|pandas.DataFrame] arrays: arrays to split
    """
    assert len(arrays) > 0, "at least one array should be passed"
    length = len(arrays[0])
    for array in arrays:
        assert len(array) == length, "different size"
    train_indices, test_indices = sklearn.cross_validation.train_test_split(range(length), **kw_args)
    result = []
    for array in arrays:
        if isinstance(array, pandas.DataFrame):
            result.append(array.iloc[train_indices, :])
            result.append(array.iloc[test_indices, :])
        else:
            result.append(array[train_indices])
            result.append(array[test_indices])
    return result


def weighted_percentile(array, percentiles, sample_weight=None, array_sorted=False, old_style=False):
    """ Very close to numpy.precentile, but supports weights.
    NOTE: percentiles should be in [0, 1]!
    :param array: numpy.array with data
    :param percentiles: array-like with many percentiles
    :param sample_weight: array-like of the same length as `array`
    :param array_sorted: bool, if True, then will avoid sorting
    :param old_style: if True, will correct output to be consistent with numpy.percentile.
    :return: numpy.array with computed percentiles.
    """
    array = numpy.array(array)
    percentiles = numpy.array(percentiles)
    sample_weight = check_sample_weight(array, sample_weight)
    assert numpy.all(percentiles >= 0) and numpy.all(percentiles <= 1), 'Percentiles should be in [0, 1]'

    if not array_sorted:
        array, sample_weight = reorder_by_first(array, sample_weight)

    weighted_quantiles = numpy.cumsum(sample_weight) - 0.5 * sample_weight
    if old_style:
        # To be convenient with numpy.percentile
        weighted_quantiles -= weighted_quantiles[0]
        weighted_quantiles /= weighted_quantiles[-1]
    else:
        weighted_quantiles /= numpy.sum(sample_weight)
    return numpy.interp(percentiles, weighted_quantiles, array)


def build_normalizer(signal, sample_weight=None):
    """Prepares normalization function for some set of values
    transforms it to uniform distribution from [0, 1]. Example of usage:
    >>>normalizer = build_normalizer(signal)
    >>>pylab.hist(normalizer(background))
    >>># this one should be uniform in [0,1]
    >>>pylab.hist(normalizer(signal))
    Parameters:
    :param numpy.array signal: shape = [n_samples] with floats
    :param numpy.array sample_weight: shape = [n_samples], non-negative weights associated to events.
    """
    sample_weight = check_sample_weight(signal, sample_weight)
    assert numpy.all(sample_weight >= 0.), 'sample weight must be non-negative'
    signal, sample_weight = reorder_by_first(signal, sample_weight)
    predictions = numpy.cumsum(sample_weight) / numpy.sum(sample_weight)

    def normalizing_function(data):
        return numpy.interp(data, signal, predictions)

    return normalizing_function


def compute_cut_for_efficiency(efficiency, mask, y_pred, sample_weight=None):
    """ Computes such cut(s), that provide given signal efficiency.
    :type efficiency: float or numpy.array with target efficiencies, shape = [n_effs]
    :type mask: array-like, shape = [n_samples], True for needed classes
    :type y_pred: array-like, shape = [n_samples], predictions or scores (float)
    :type sample_weight: None | array-like, shape = [n_samples]
    :return: float or numpy.array, shape = [n_effs]
    """
    sample_weight = check_sample_weight(mask, sample_weight)
    assert len(mask) == len(y_pred), 'lengths are different'
    efficiency = numpy.array(efficiency)
    is_signal = mask > 0.5
    y_pred, sample_weight = y_pred[is_signal], sample_weight[is_signal]
    return weighted_percentile(y_pred, 1. - efficiency, sample_weight=sample_weight)


def compute_bdt_cut(target_efficiency, y_true, y_pred, sample_weight=None):
    """Computes cut which gives fixed efficiency.
    :type target_efficiency: float from 0 to 1 or numpy.array with floats in [0,1]
    :type y_true: numpy.array, of zeros and ones, shape = [n_samples]
    :type y_pred: numpy.array, prediction probabilities returned by classifier, shape = [n_samples]
    """
    assert len(y_true) == len(y_pred), "different size"
    signal_proba = y_pred[y_true > 0.5]
    percentiles = 1. - target_efficiency
    sig_weights = None if sample_weight is None else sample_weight[y_true > 0.5]
    return weighted_percentile(signal_proba, percentiles, sample_weight=sig_weights)


# region Knn-related things

# TODO update interface here and in all other places to work
# without columns
def computeSignalKnnIndices(uniform_variables, dataframe, is_signal, n_neighbors=50):
    """For each event returns the knn closest signal(!) events. No matter of what class the event is.
    :type uniform_variables: list of names of variables, using which we want to compute the distance
    :type dataframe: pandas.DataFrame, should contain these variables
    :type is_signal: numpy.array, shape = [n_samples] with booleans
    :rtype numpy.array, shape [len(dataframe), knn], each row contains indices of closest signal events
    """
    assert len(dataframe) == len(is_signal), "Different lengths"
    signal_indices = numpy.where(is_signal)[0]
    for variable in uniform_variables:
        assert variable in dataframe.columns, "Dataframe is missing %s column" % variable
    uniforming_features_of_signal = numpy.array(dataframe.ix[is_signal, uniform_variables])
    neighbours = NearestNeighbors(n_neighbors=n_neighbors, algorithm='kd_tree').fit(uniforming_features_of_signal)
    _, knn_signal_indices = neighbours.kneighbors(dataframe[uniform_variables])
    return numpy.take(signal_indices, knn_signal_indices)


def computeKnnIndicesOfSameClass(uniform_variables, X, y, n_neighbours=50):
    """Works as previous function, but returns the neighbours of the same class as element
    :param list[str] uniform_variables: the names of columns"""
    assert len(X) == len(y), "different size"
    result = numpy.zeros([len(X), n_neighbours], dtype=numpy.int)
    for label in set(y):
        is_signal = y == label
        label_knn = computeSignalKnnIndices(uniform_variables, X, is_signal, n_neighbours)
        result[is_signal, :] = label_knn[is_signal, :]
    return result


# endregion


def smear_dataset(testX, smeared_variables=None, smearing_factor=0.1):
    """For the selected features 'smears' them in dataset,
    pay attention, that only float feature can be smeared by now.
    If smeared variables is None, all the features are smeared"""
    assert isinstance(testX, pandas.DataFrame), "the passed object is not of type pandas.DataFrame"
    testX = pandas.DataFrame.copy(testX)
    if smeared_variables is None:
        smeared_variables = testX.columns
    for var in smeared_variables:
        assert var in testX.columns, "The variable %s was not found in dataframe"
    result = pandas.DataFrame.copy(testX)
    for var in smeared_variables:
        sigma = math.sqrt(numpy.var(result[var]))
        result[var] += RandomState().normal(0, smearing_factor * sigma, size=len(result))
    return result


def memory_usage():
    """Memory usage of the current process in bytes. Created for notebooks.
    This will only work on systems with a /proc file system (like Linux)."""
    result = {'peak': 0, 'rss': 0}
    with open('/proc/self/status') as status:
        for line in status:
            parts = line.split()
            key = parts[0][2:-1].lower()
            if key in result:
                result[key] = "{:,} kB".format(int(parts[1]))
    return result


def indices_of_values(array):
    """For each value in array returns indices with this value
    :param array: numpy.array with 1-dimensional initial data
    :return: sequence of tuples (value, indices_with_this_value), sequence is ordered by value
    """
    indices = numpy.argsort(array)
    sorted_array = array[indices]
    diff = numpy.nonzero(numpy.ediff1d(sorted_array))[0]
    limits = [0] + list(diff + 1) + [len(array)]
    for i in range(len(limits) - 1):
        yield sorted_array[limits[i]], indices[limits[i]: limits[i + 1]]


def print_header(text, level=3):
    """
    Function to be used in notebooks to display headers not just plain text
    :param text: str or object to print its __repr__
    :param level: int, from 1 to 6 (1st, 2nd, 3rd order header)
    """
    from IPython.display import display_html

    display_html("<h{level}>{header}</h{level}>".format(header=text, level=level), raw=True)


def take_features(X, features):
    """
    Takes features from dataset.
    :param X: numpy.array or pandas.DataFrame
    :param features: list of strings (if pandas.DataFrame) or list of ints
    :return: pandas.DataFrame or numpy.array with the same length.
    NOTE: may return view to original data!
    """
    from numbers import Number

    are_strings = all([isinstance(feature, str) for feature in features])
    are_numbers = all([isinstance(feature, Number) for feature in features])
    if are_strings and isinstance(X, pandas.DataFrame):
        return X.ix[:, features]
    elif are_numbers:
        return numpy.array(X)[:, features]
    else:
        raise NotImplementedError("Can't take features {} from object of type {}".format(features, type(X)))


def check_sample_weight(y_true, sample_weight):
    """
    Checks the weights, returns normalized version
    :param y_true: numpy.array of shape [n_samples]
    :param sample_weight: array-like of shape [n_samples] or None
    :returns: numpy.array with weights of shape [n_samples]"""
    if sample_weight is None:
        return numpy.ones(len(y_true), dtype=numpy.float)
    else:
        sample_weight = numpy.array(sample_weight, dtype=numpy.float)
        assert len(y_true) == len(sample_weight), \
            "The length of weights is different: not {0}, but {1}".format(len(y_true), len(sample_weight))
        return sample_weight


def check_xyw(X, y, sample_weight=None):
    """
    Checks parameters of classifier / loss / metrics
    :param X: array-like of shape [n_samples, n_features] (numpy.array or pandas.DataFrame)
    :param y: array-like of shape [n_samples]
    :param sample_weight: None or array-like of shape [n_samples]
    :return:
    """
    from sklearn.utils.validation import column_or_1d
    y = column_or_1d(y)
    sample_weight = check_sample_weight(y, sample_weight=sample_weight)
    assert len(X) == len(y), 'Lengths are different'
    if not (isinstance(X, pandas.DataFrame) or (isinstance(X, numpy.ndarray))):
        X = numpy.array(X)
    return X, y, sample_weight


