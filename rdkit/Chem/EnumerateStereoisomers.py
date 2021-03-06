import six
import random
from rdkit import Chem
from rdkit.Chem.rdDistGeom import EmbedMolecule

class StereoEnumerationOptions(object):
    """
          - tryEmbedding: if set the process attempts to generate a standard RDKit distance geometry
            conformation for the stereisomer. If this fails, we assume that the stereoisomer is
            non-physical and don't return it. NOTE that this is computationally expensive and is
            just a heuristic that could result in stereoisomers being lost.

          - onlyUnassigned: if set (the default), stereocenters which have specified stereochemistry
            will not be perturbed

          - maxIsomers: the maximum number of isomers to yield, if the
            number of possible isomers is greater than maxIsomers, a
            random subset will be yielded. If 0, all isomers are
            yielded. Since every additional stereo center doubles the
            number of results (and execution time) it's important to
            keep an eye on this.
    """
    __slots__ = ('tryEmbedding', 'onlyUnassigned', 'maxIsomers', 'rand')
    def __init__(self, tryEmbedding = False, onlyUnassigned = True,
                 maxIsomers = 1024, rand = None):
        self.tryEmbedding = tryEmbedding
        self.onlyUnassigned = onlyUnassigned
        self.maxIsomers = maxIsomers
        self.rand = rand

class _BondFlipper(object):
    def __init__(self, bond):
        self.bond = bond

    def flip(self, flag):
        if flag:
            self.bond.SetStereo(Chem.BondStereo.STEREOCIS)
        else:
            self.bond.SetStereo(Chem.BondStereo.STEREOTRANS)

class _AtomFlipper(object):
    def __init__(self, atom):
        self.atom = atom

    def flip(self, flag):
        if flag:
            self.atom.SetChiralTag(Chem.ChiralType.CHI_TETRAHEDRAL_CW)
        else:
            self.atom.SetChiralTag(Chem.ChiralType.CHI_TETRAHEDRAL_CCW)

def _getFlippers(mol, options):
    Chem.FindPotentialStereoBonds(mol)

    flippers = []
    for atom in mol.GetAtoms():
        if atom.HasProp("_ChiralityPossible"):
            if (not options.onlyUnassigned or
                atom.GetChiralTag() == Chem.ChiralType.CHI_UNSPECIFIED):
                flippers.append(_AtomFlipper(atom))

    for bond in mol.GetBonds():
        bstereo = bond.GetStereo()
        if bstereo != Chem.BondStereo.STEREONONE:
            if (not options.onlyUnassigned or
                bstereo == Chem.BondStereo.STEREOANY):
                flippers.append(_BondFlipper(bond))

    return flippers

class _RangeBitsGenerator(object):
    def __init__(self, nCenters):
        self.nCenters = nCenters

    def __iter__(self):
        for val in six.moves.range(2**self.nCenters):
            yield val

class _UniqueRandomBitsGenerator(object):
    def __init__(self, nCenters, maxIsomers, rand):
        self.nCenters = nCenters
        self.maxIsomers = maxIsomers
        self.rand = rand
        self.already_seen = set()

    def __iter__(self):
        # note: important that this is not 'while True' otherwise it
        # would be possible to have an infinite loop caused by all
        # isomers failing the embedding process
        while len(self.already_seen) < 2**self.nCenters:
            bits = self.rand.getrandbits(self.nCenters)
            if bits in self.already_seen:
                continue

            self.already_seen.add(bits)
            yield bits

def EnumerateStereoisomers(m, options=StereoEnumerationOptions(), verbose=False):
    """ returns a generator that yields possible stereoisomers for a molecule

    Arguments:
      - m: the molecule to work with
      - verbose: toggles how verbose the output is

    A small example with 3 chiral atoms and 1 chiral bond (16 theoretical stereoisomers):
    >>> from rdkit import Chem
    >>> from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions
    >>> m = Chem.MolFromSmiles('BrC=CC1OC(C2)(F)C2(Cl)C1')
    >>> isomers = tuple(EnumerateStereoisomers(m))
    >>> len(isomers)
    16
    >>> for smi in sorted(Chem.MolToSmiles(x, isomericSmiles=True) for x in isomers):
    ...     print(smi)
    ...
    F[C@@]12C[C@@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@@]12C[C@@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@@]12C[C@@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@@]12C[C@@]1(Cl)C[C@H](/C=C\Br)O2
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@@]12C[C@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@@]12C[C@]1(Cl)C[C@H](/C=C\Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@]12C[C@@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@]12C[C@@]1(Cl)C[C@H](/C=C\Br)O2
    F[C@]12C[C@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@]12C[C@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@]12C[C@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@]12C[C@]1(Cl)C[C@H](/C=C\Br)O2

    Because the molecule is constrained, not all of those isomers can
    actually exist. We can check that:
    >>> opts = StereoEnumerationOptions(tryEmbedding=True)
    >>> isomers = tuple(EnumerateStereoisomers(m, options=opts))
    >>> len(isomers)
    8
    >>> for smi in sorted(Chem.MolToSmiles(x,isomericSmiles=True) for x in isomers):
    ...     print(smi)
    ...
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@@]12C[C@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@@]12C[C@]1(Cl)C[C@H](/C=C\Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@]12C[C@@]1(Cl)C[C@H](/C=C/Br)O2
    F[C@]12C[C@@]1(Cl)C[C@H](/C=C\Br)O2

    By default the code only expands unspecified stereocenters:
    >>> m = Chem.MolFromSmiles('BrC=C[C@H]1OC(C2)(F)C2(Cl)C1')
    >>> isomers = tuple(EnumerateStereoisomers(m))
    >>> len(isomers)
    8
    >>> for smi in sorted(Chem.MolToSmiles(x,isomericSmiles=True) for x in isomers):
    ...     print(smi)
    ...
    F[C@@]12C[C@@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@@]12C[C@@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@@]12C[C@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@]12C[C@@]1(Cl)C[C@@H](/C=C\Br)O2
    F[C@]12C[C@]1(Cl)C[C@@H](/C=C/Br)O2
    F[C@]12C[C@]1(Cl)C[C@@H](/C=C\Br)O2

    But we can change that behavior:
    >>> opts = StereoEnumerationOptions(onlyUnassigned=False)
    >>> isomers = tuple(EnumerateStereoisomers(m, options=opts))
    >>> len(isomers)
    16

    Since the result is a generator, we can allow exploring at least parts of very
    large result sets:
    >>> m = Chem.MolFromSmiles('Br' + '[CH](Cl)' * 20 + 'F')
    >>> opts = StereoEnumerationOptions(maxIsomers=0)
    >>> isomers = EnumerateStereoisomers(m, options=opts)
    >>> for x in range(5):
    ...   print(Chem.MolToSmiles(next(isomers),isomericSmiles=True))
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)Br
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)Br
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)Br
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@H](Cl)Br
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)Br

    Or randomly sample a small subset:
    >>> m = Chem.MolFromSmiles('Br' + '[CH](Cl)' * 20 + 'F')
    >>> opts = StereoEnumerationOptions(maxIsomers=3)
    >>> isomers = EnumerateStereoisomers(m, options=opts)
    >>> for smi in sorted(Chem.MolToSmiles(x, isomericSmiles=True) for x in isomers):
    ...     print(smi)
    F[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@@H](Cl)Br
    F[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)Br
    F[C@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@@H](Cl)[C@H](Cl)[C@@H](Cl)Br
    """

    tm = Chem.Mol(m)
    flippers = _getFlippers(tm, options)
    nCenters = len(flippers)
    if not nCenters:
        yield tm
        return

    if (options.maxIsomers == 0 or
        2**nCenters <= options.maxIsomers):
        bitsource = _RangeBitsGenerator(nCenters)
    else:
        if options.rand is None:
            # deterministic random seed invariant to input atom order
            seed = hash(tuple(sorted([(a.GetDegree(), a.GetAtomicNum()) for a in tm.GetAtoms()])))
            rand = random.Random(seed)
        elif isinstance(options.rand, random.Random):
            # other implementations of Python random number generators
            # can inherit from this class to pick up utility methods
            rand = options.rand
        else:
            rand = random.Random(options.rand)

        bitsource = _UniqueRandomBitsGenerator(nCenters, options.maxIsomers, rand)

    numIsomers = 0
    for bitflag in bitsource:
        for i in range(nCenters):
            flag = bool(bitflag & (1 << i))
            flippers[i].flip(flag)

        isomer = Chem.Mol(tm)
        if options.tryEmbedding:
            ntm = Chem.AddHs(isomer)
            cid = EmbedMolecule(ntm, randomSeed=bitflag)
            if cid >= 0:
                conf = Chem.Conformer(isomer.GetNumAtoms())
                for aid in range(isomer.GetNumAtoms()):
                    conf.SetAtomPosition(aid, ntm.GetConformer().GetAtomPosition(aid))
                isomer.AddConformer(conf)
        else:
            cid = 1
        if cid >= 0:
            yield isomer
            numIsomers += 1
            if options.maxIsomers != 0 and numIsomers >= options.maxIsomers:
                break
        elif verbose:
            print("%s    failed to embed" % (Chem.MolToSmiles(isomer, isomericSmiles=True)))


