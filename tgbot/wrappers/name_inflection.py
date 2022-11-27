from tgbot.enums import Gender


try:
    import pymorphy2
except ImportError:
    pymorphy2 = None

CASES = ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']


class NameString(str):

    def __new__(cls, components):
        new_components = []
        for component in components:
            if isinstance(component, NameString):
                new_components.extend(component.components)
            else:
                new_components.append(component)
        r = str.__new__(cls, ''.join(new_components))
        r.components = new_components
        return r

    def __matmul__(self, obj):
        elements = []
        for component in self.components:
            if isinstance(component, NameWord):
                elements.append(component @ obj)
            else:
                elements.append(component)
        return ''.join(elements)

    @property
    def gender(self):
        for component in self.components:
            if isinstance(component, NameWord):
                return component.gender


class NameWord(str):
    morph = None

    def __new__(cls, *args, **kwargs):
        r = str.__new__(cls, *args, **kwargs)
        r._cache = None
        r._gender = None
        return r

    def __matmul__(self, obj):
        if not (isinstance(obj, int) and 0 <= obj <= 5):
            raise ValueError('Invalid query. Pass an integer from 0 to 5')
        if self._cache is None:
            self.parse()
        return self._cache[obj]

    @property
    def gender(self):
        if self._gender is None:
            self.parse()
        return self._gender

    @classmethod
    def initialize_morph(cls):
        cls.morph = pymorphy2.MorphAnalyzer()

    def parse(self):
        if self.__class__.morph is None:
            self.initialize_morph()
        results = self.morph.parse(self)
        result = None
        for r in results:
            if r.tag.case == CASES[0]:
                result = r
                break
        if result is None:
            forms = None
        else:
            # Sometimes words of various genders get into pymorph lexeme.
            # Therefore, we will simply iterate over all lexemes from all parsing, and save the necessary.
            # Gender can come in handy later in external code,
            # for example, to choose the form of a verb.
            gender = result.tag.gender
            self._gender = Gender.MALE if gender == 'masc' else Gender.Female
            lexemes = []
            [lexemes.extend(r.lexeme) for r in results]
            forms = []
            cases_iter = iter(CASES)
            next_case = next(cases_iter)
            for form in lexemes:
                if form.tag.gender == gender and form.tag.case == next_case:
                    forms.append(form.word.capitalize())
                    if len(forms) == 6:
                        break
                    try:
                        next_case = next(cases_iter)
                    except StopIteration:
                        break
            if len(forms) != 6:
                forms = None
        if forms is None:
            forms = [str(self)] * 6
        self._cache = forms


def wrap_name_string(string):
    string = string.strip()
    if ' ' not in string:
        return NameWord(string)
    components = [NameWord(c) for c in string.split()]
    result = [' '] * (len(components) *2 -1)
    result[::2] = components
    return NameString(result)
