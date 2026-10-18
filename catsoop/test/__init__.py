import unittest
import warnings

from . import setup_data


class CATSOOPTest(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", ImportWarning)
