"""Small vocabulary classes rebuilt from convert.py's JSON.

Behaviour mirrors stanza.models.common.vocab (Stanza 1.14.0, Apache-2.0):
BaseVocab.unit2id, CompositeVocab unmap and so on.
"""

PAD, UNK, EMPTY, ROOT = '<PAD>', '<UNK>', '<EMPTY>', '<ROOT>'
PAD_ID, UNK_ID, EMPTY_ID, ROOT_ID = 0, 1, 2, 3
VOCAB_PREFIX_SIZE = 4


class BaseVocab:
    def __init__(self, d):
        assert d["kind"] == "base"
        self.lower = d["lower"]
        self._id2unit = d["id2unit"]
        self._unit2id = {w: i for i, w in enumerate(self._id2unit)}

    def normalize_unit(self, unit):
        if unit is None:
            return unit
        if self.lower:
            return unit.lower()
        return unit

    def unit2id(self, unit):
        unit = self.normalize_unit(unit)
        return self._unit2id.get(unit, UNK_ID)

    def id2unit(self, i):
        return self._id2unit[i]

    def map(self, units):
        return [self.unit2id(x) for x in units]

    def unmap(self, ids):
        return [self._id2unit[x] for x in ids]

    def __len__(self):
        return len(self._id2unit)

    @property
    def size(self):
        return len(self._id2unit)


class PretrainedWordVocab(BaseVocab):
    def normalize_unit(self, unit):
        unit = super().normalize_unit(unit)
        if unit:
            unit = unit.replace(" ", "\xa0")
        return unit


class CompositeVocab:
    """Only the decode direction (ids -> 'key=value|key=value') is needed."""

    def __init__(self, d):
        assert d["kind"] == "composite"
        self.sep = d["sep"]
        self.keyed = d["keyed"]
        self.keys = d["keys"]
        self._id2unit = d["id2unit"]          # list (per key) of list of values

    def lens(self):
        return [len(x) for x in self._id2unit]

    def __len__(self):
        return len(self._id2unit)

    def id2unit(self, ids):
        items = []
        for v, k, vals in zip(ids, self.keys, self._id2unit):
            if v == EMPTY_ID:
                continue
            if self.keyed:
                items.append("{}={}".format(k, vals[v]))
            else:
                items.append(vals[v])
        res = self.sep.join(items)
        if res == "":
            res = "_"
        return res

    def unmap(self, ids):
        return [self.id2unit(x) for x in ids]
