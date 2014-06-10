import numpy
import pandas
from sklearn.base import BaseEstimator, ClassifierMixin, clone


class HidingClassifier(BaseEstimator, ClassifierMixin):

    def __init__(self, train_variables=None, base_estimator=None):
        """This is a dumb meta-classifier, which uses only subset of variables to train
        base classifier and to estimate result"""
        self.train_variables = train_variables
        self.base_estimator = base_estimator

    def fit(self, X, y):
        assert self.base_estimator is not None, "base estimator was not set"
        self._trained_estimator = clone(self.base_estimator)
        self._trained_estimator.fit(X[self.train_variables], y)

    def predict(self, X):
        return self._trained_estimator.predict(X[self.train_variables])

    def predict_proba(self, X):
        return self._trained_estimator.predict_proba(X[self.train_variables])

    def staged_predict_proba(self, X):
        return self._trained_estimator.staged_predict_proba(X[self.train_variables])


class FeatureSplitter(BaseEstimator, ClassifierMixin):
    def __init__(self, feature_name, base_estimator):
        self.base_estimator = base_estimator
        self.feature_name = feature_name

    def fit(self, X, y, sample_weight=None):
        column = numpy.array(X[self.feature_name])
        self.values = set(column)
        for value in self.values:
            x_part = X[self.values == value]
            stayed_columns = pandas.DataFrame.dropna(x_part, axis=1).columns
            x_part[stayed_columns]