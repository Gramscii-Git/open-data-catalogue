"""A stored structure error is permanent only as the bare answer a provider rule declares."""

import unittest

from catalogue.structure_errors import declared_permanent

TEMPLATE = ("An error occured while trying to retrieve mapping set for dataflow: {agency}+{id}+{version}: \n"
            " Dataflow 'urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow={agency}:{id}({version})' doesn't contain a mapping set")
ISTAT = {"id": "istat", "driver": "sdmx", "extra": {"dataflow_permanent_errors": [{"status": 500, "body_template": TEMPLATE}]}}
BODY = ("An error occured while trying to retrieve mapping set for dataflow: IT1+115_362+1.0: \n"
        " Dataflow 'urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=IT1:115_362(1.0)' doesn't contain a mapping set")


class DeclaredPermanentErrors(unittest.TestCase):
    def test_only_the_bare_matching_answer_is_permanent(self):
        self.assertTrue(declared_permanent(ISTAT, "istat answered 500: " + BODY))
        self.assertFalse(declared_permanent(ISTAT, "istat/rest: request failed after 8 attempts: istat answered 500: " + BODY))
        self.assertFalse(declared_permanent(ISTAT, "istat answered 502: " + BODY))
        self.assertFalse(declared_permanent(ISTAT, "istat answered 500: " + BODY.replace("IT1:115_362", "IT1:115_363")))
        self.assertFalse(declared_permanent(ISTAT, "istat answered 500: " + BODY + " later"))
        self.assertFalse(declared_permanent({"id": "dvns", "driver": "dvns", "extra": {}}, "dvns answered 500: " + BODY))
