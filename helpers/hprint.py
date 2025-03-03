"""
Import as:

import helpers.hprint as hprint
"""

import inspect
import logging
import re
import sys
from typing import Any, Callable, Dict, Iterable, List, Match, Optional, cast

import helpers.hdbg as hdbg

# Avoid dependency from other `helpers` modules to prevent import cycles.


_LOG = logging.getLogger(__name__)

# Mute this module unless we want to debug it.
_LOG.setLevel(logging.INFO)


# #############################################################################
# Debug output
# #############################################################################

_COLOR_MAP = {
    "blue": 94,
    "green": 92,
    "white": 0,
    "purple": 95,
    "red": 91,
    "yellow": 33,
    # Blu.
    "DEBUG": 34,
    # Cyan.
    "INFO": 36,
    # Yellow.
    "WARNING": 33,
    # Red.
    "ERROR": 31,
    # White on red background.
    "CRITICAL": 41,
}


def color_highlight(text: str, color: str) -> str:
    """
    Return a colored string.
    """
    prefix = "\033["
    suffix = "\033[0m"
    hdbg.dassert_in(color, _COLOR_MAP)
    color_code = _COLOR_MAP[color]
    txt = f"{prefix}{color_code}m{text}{suffix}"
    return txt


def clear_screen() -> None:
    print((chr(27) + "[2J"))


def line(char: Optional[str] = None, num_chars: Optional[int] = None) -> str:
    """
    Return a line with the desired character.
    """
    char = "#" if char is None else char
    num_chars = 80 if num_chars is None else num_chars
    return char * num_chars


# TODO(gp): -> Use *args instead of forcing to build a string to simplify the caller.
def frame(
    message: str,
    *,
    char1: Optional[str] = None,
    num_chars: Optional[int] = None,
    char2: Optional[str] = None,
    thickness: int = 1,
) -> str:
    """
    Print a frame around a message.
    """
    # Fill in the default values.
    if char1 is None:
        # User didn't specify any char.
        char1 = char2 = "#"
    elif char1 is not None and char2 is None:
        # User specified only one char.
        char2 = char1
    elif char1 is None and char2 is not None:
        # User specified the second char, but not the first.
        hdbg.dfatal(f"Invalid char1='{char1}' char2='{char2}'")
    else:
        # User specified both chars. Nothing to do.
        pass
    num_chars = 80 if num_chars is None else num_chars
    # Sanity check.
    hdbg.dassert_lte(1, thickness)
    hdbg.dassert_eq(len(char1), 1)
    hdbg.dassert_eq(len(char2), 1)
    hdbg.dassert_lte(1, num_chars)
    # Build the return value.
    ret = (
        (line(char1, num_chars) + "\n") * thickness
        + message
        + "\n"
        + (line(char2, num_chars) + "\n") * thickness
    ).rstrip("\n")
    return ret


def prepend(txt: str, prefix: str) -> str:
    """
    Add `prefix` before each line of the string `txt`.
    """
    lines = [prefix + curr_line for curr_line in txt.split("\n")]
    res = "\n".join(lines)
    return res


# TODO(gp): It should use *.
def indent(txt: str, num_spaces: int = 2) -> str:
    """
    Add `num_spaces` spaces before each line of the passed string.
    """
    spaces = " " * num_spaces
    txt_out = []
    for curr_line in txt.split("\n"):
        if curr_line.lstrip().rstrip() == "":
            # Do not prepend any space to a line with only white characters.
            txt_out.append("")
            continue
        txt_out.append(spaces + curr_line)
    res = "\n".join(txt_out)
    return res


# TODO(gp): It should use *.
def dedent(txt: str, remove_empty_leading_trailing_lines: bool = True) -> str:
    """
    Remove from each line the minimum number of spaces to align the text on the
    left.

    It is the opposite of `indent()`.

    :param remove_empty_leading_trailing_lines: if True, remove all the empty lines
        at the beginning and at the end
    """
    if remove_empty_leading_trailing_lines:
        txt = txt.rstrip("\n").lstrip("\n")
    # Find the minimum number of leading spaces.
    min_num_spaces = None
    for curr_line in txt.split("\n"):
        _LOG.debug("min_num_spaces=%s: curr_line='%s'", min_num_spaces, curr_line)
        # Skip empty lines.
        if curr_line.lstrip().rstrip() == "":
            _LOG.debug("  -> Skipping empty line")
            continue
        m = re.search(r"^(\s*)", curr_line)
        hdbg.dassert(m)
        m: Match[Any]
        curr_num_spaces = len(m.group(1))
        _LOG.debug("  -> curr_num_spaces=%s", curr_num_spaces)
        if min_num_spaces is None or curr_num_spaces < min_num_spaces:
            min_num_spaces = curr_num_spaces
    _LOG.debug("min_num_spaces=%s", min_num_spaces)
    #
    txt_out = []
    for curr_line in txt.split("\n"):
        _LOG.debug("curr_line='%s'", curr_line)
        # Skip empty lines.
        if curr_line.lstrip().rstrip() == "":
            txt_out.append("")
            continue
        hdbg.dassert_lte(min_num_spaces, len(curr_line))
        txt_out.append(curr_line[min_num_spaces:])
    res = "\n".join(txt_out)
    return res


def align_on_left(txt: str) -> str:
    """
    Remove all leading/trailing spaces for each line.
    """
    txt_out = []
    for curr_line in txt.split("\n"):
        curr_line = curr_line.rstrip(" ").lstrip(" ")
        txt_out.append(curr_line)
    res = "\n".join(txt_out)
    return res


# TODO(gp): Is this used? It looks very thin.
def remove_empty_lines_from_string_list(arr: List[str]) -> List[str]:
    """
    Remove empty lines from a list of strings.
    """
    arr = [line for line in arr if line.rstrip().lstrip()]
    return arr


# TODO(gp): It would be nice to have a decorator to go from / to array of
#  strings.
def remove_empty_lines(txt: str) -> str:
    """
    Remove empty lines from a multi-line string.
    """
    arr = txt.split("\n")
    arr = remove_empty_lines_from_string_list(arr)
    txt = "\n".join(arr)
    return txt


def vars_to_debug_string(vars_as_str: List[str], locals_: Dict[str, Any]) -> str:
    """
    Create a string with var name -> var value.

    E.g., ["var1", "var2"] is converted into: ``` var1=... var2=... ```
    """
    txt = []
    for var in vars_as_str:
        txt.append(var + "=")
        txt.append(indent(str(locals_[var])))
    return "\n".join(txt)


# #############################################################################
# Pretty print data structures.
# #############################################################################


def thousand_separator(v: float) -> str:
    v = "{0:,}".format(v)
    return v


# TODO(gp): -> to_percentage
def perc(
    a: float,
    b: float,
    only_perc: bool = False,
    invert: bool = False,
    num_digits: int = 2,
    use_thousands_separator: bool = False,
) -> str:
    """
    Calculate percentage a / b as a string.

    Asserts 0 <= a <= b. If true, returns a/b to `num_digits` decimal places.

    :param a: numerator
    :param b: denominator
    :param only_perc: return only the percentage, without the original numbers
    :param invert: assume the fraction is (b - a) / b
        This is useful when we want to compute the complement of a count.
    :param use_thousands_separator: report the numbers using thousands separator
    :return: string with a/b
    """
    hdbg.dassert_lte(0, a)
    hdbg.dassert_lte(a, b)
    if use_thousands_separator:
        a_str = str("{0:,}".format(a))
        b_str = str("{0:,}".format(b))
    else:
        a_str = str(a)
        b_str = str(b)
    if invert:
        a = b - a
    hdbg.dassert_lte(0, num_digits)
    if only_perc:
        fmt = "%." + str(num_digits) + "f%%"
        ret = fmt % (float(a) / b * 100.0)
    else:
        fmt = "%s / %s = %." + str(num_digits) + "f%%"
        ret = fmt % (a_str, b_str, float(a) / b * 100.0)
    return ret


def round_digits(
    v: float, num_digits: int = 2, use_thousands_separator: bool = False
) -> str:
    """
    Round digit returning a string representing the formatted number.

    :param v: value to convert
    :param num_digits: number of digits to represent v on
            None is (Default value = 2)
    :param use_thousands_separator: use "," to separate thousands (Default value = False)
    :returns: str with formatted value
    """
    if (num_digits is not None) and isinstance(v, float):
        fmt = "%0." + str(num_digits) + "f"
        res = float(fmt % v)
    else:
        res = v
    if use_thousands_separator:
        res = "{0:,}".format(res)  # type: ignore
    res_as_str = str(res)
    return res_as_str


# #############################################################################
# Logging helpers
# #############################################################################


# TODO(gp): Move this to hdbg.hlogging, but there are dependencies from this file.

# https://stackoverflow.com/questions/2749796 has some solutions to find the
# name of variables from the caller.


def to_str(expression: str, frame_lev: int = 1) -> str:
    """
    Return a string with the value of a variable / expression / multiple
    variables.

    If expression is a space-separated compound expression, convert it into
    `exp1=val1, exp2=val2, ...`.

    This is similar to Python 3.8 f-string syntax `f"{foo=} {bar=}"`.
    We don't want to force to use Python 3.8 just for this feature.

    >>> x = 1
    >>> to_str("x+1")
    x+1=2
    """
    # TODO(gp): If we pass an object it would be nice to find the name of it.
    # E.g., https://github.com/pwwang/python-varname
    hdbg.dassert_isinstance(expression, str)
    if " " in expression:
        # If expression is a list of space-separated expression, convert each in a
        # string.
        exprs = [v.lstrip().rstrip() for v in expression.split(" ")]
        _to_str = lambda x: to_str(x, frame_lev=frame_lev + 2)
        return ", ".join(list(map(_to_str, exprs)))
    frame_ = sys._getframe(frame_lev)  # pylint: disable=protected-access
    ret = (
        expression
        + "="
        + repr(eval(expression, frame_.f_globals, frame_.f_locals))
    )
    return ret


# TODO(timurg): In order to replace `hprint.to_str` function,
# `frame level`(see `hprint.to_str`) should be implemented,
# otherwise `helpers/test/test_printing.py::Test_log::test2-4` will fail,
# see CmTask #1554.


def to_str2(*variables_values: Any) -> str:
    """
    Return a string with name and value of variables passed to the function as
    `name=value`.

    E.g.,:
    ```
    a = 5
    b = "hello"
    n = 2
    to_str2(a, b, n+1)
    ```
    returns a string "a=5, b=hello, n+1=2".

    Limitations: can't work with an argument that contains parenthesis,
    e.g.,: `to_str(to_str(a, b), c)`.

    Dependencies: funtion call index depends on the Python version, `frame.lineno` is
       - Last argument line in Python >=3.6 and < 3.9
       - Function call line in Python 3.9 and above

    :param variables_values: variables to convert into "name=value" string
    :return: string e.g., `a=1, b=2`
    """
    # Check parameters.
    hdbg.dassert_lte(1, len(variables_values))
    # Get frame object for the caller’s stack frame.
    frame_ = inspect.currentframe()
    # Get a list of frame records for a frame and all outer frames.
    frames = inspect.getouterframes(frame_)
    # Get first outer frame - from where function was called, and the current one.
    frame_above, current_frame = frames[1], frames[0]
    # Get source code starting from line where current function was called.
    source_code_lines, _ = inspect.findsource(frame_above.frame)
    # Line number start from 1, while index starts with 0.
    call_line_index = frame_above.lineno - 1
    stripped_code_lines = [
        line.strip() for line in source_code_lines[call_line_index:]
    ]
    source_code_string = "".join(stripped_code_lines)
    # Find the name of the current function in the code.
    regex = rf"{current_frame.function}\((.*?)\)"
    matches = re.findall(regex, source_code_string)
    hdbg.dassert_ne(
        len(matches),
        0,
        "No arguments found in the source code for %s",
        str(current_frame.function),
    )
    # Only fist match from regex is needed.
    variables_names_str = matches[0]
    variables_names = variables_names_str.split(",")
    hdbg.dassert_eq(
        len(variables_names),
        len(variables_values),
        "Number of vars and values is not equal: var_names=%s, val_names=%s",
        str(variables_names),
        str(variables_values),
    )
    # Package the name and the value of the variables in the return string.
    output = []
    for name, value in zip(variables_names, variables_values):
        output.append(f"{name.strip()}={value}")
    return ", ".join(output)


def log(logger: logging.Logger, verbosity: int, *vals: Any) -> None:
    """
    log(_LOG, logging.DEBUG, "ticker", "exchange")

    is equivalent to statements like:

    _LOG.debug("%s, %s", to_str("ticker"), to_str("exchange"))
    _LOG.debug("ticker=%s, exchange=%s", ticker, exchange)
    """
    logger_verbosity = hdbg.get_logger_verbosity()
    # print("verbosity=%s logger_verbosity=%s" % (verbosity, logger_verbosity))
    # We want to avoid the overhead of converting strings, so we evaluate the
    # expressions only if we are going to print.
    if verbosity >= logger_verbosity:
        # We need to increment frame_lev since we are 2 levels deeper in the stack.
        _to_str = lambda x: to_str(x, frame_lev=3)
        num_vals = len(vals)
        if num_vals == 1:
            fstring = "%s"
            vals = _to_str(vals[0])  # type: ignore
        else:
            fstring = ", ".join(["%s"] * num_vals)
            vals = list(map(_to_str, vals))  # type: ignore
        logger.log(verbosity, fstring, vals)


# TODO(gp): Replace calls to `_LOG.debug("\n%s", hprint.frame(...)` with this.
# TODO(gp): Consider changing the signature from
#  _log_frame(_LOG, "hello", verbosity=logger.INFO))
# to
#  _log_frame(_LOG.info, "hello", ...)
# by using the first element as a Callable
def log_frame(
    logger: logging.Logger,
    fstring: str,
    *args: Any,
    level: int = 1,
    char: str = "#",
    verbosity: int = logging.DEBUG,
) -> None:
    """
    Log using a frame around the text with different number of leading `#` (or
    `char`) to organize the log visually.

    The logging output looks like:
    _log_frame(_LOG, "hello", verbosity=logger.INFO))
    ```
    07:44:51       printing            : log_frame                     : 390 :
    # #########################################################################
    # hello
    # #########################################################################
    ```

    :param txt: text to print in a frame
    :param level: number of `#` (or `char`) to prepend the logged text
    :param char: char to prepend the logged text with
    :param verbosity: logging verbosity
    """
    hdbg.dassert_isinstance(logger, logging.Logger)
    hdbg.dassert_isinstance(fstring, str)
    msg = fstring % args
    msg = msg.rstrip().lstrip()
    msg = frame(msg)
    # Prepend a `# `, if needed.
    if level > 0:
        prefix = level * char + " "
        msg = prepend(msg, prefix=prefix)
    # Add an empty space.
    msg = "\n" + msg
    logger.log(verbosity, "%s", msg)


# TODO(gp): This can be injected in `hlogger.py` and then controlled through
#  command line, e.g., `-v VERBOSE`. We should be able to tweak the verbosity
#  of each module independently.
def install_log_verb_debug(logger: logging.Logger, *, verbose: bool) -> Callable:
    """
    Create in a module a _LOG.verb_debug() that can be disabled in a
    centralized way.

    This is useful when we want to have an higher-level of verbose debugging that
    can be enabled programmatically.

    Use example:
    ```
    _LOG = logging.getLogger(__name__)
    # Assign this not to confuse the linter about a symbol that doesn't exist
    # in the code.
    _LOG.verb_debug = hprint.install_log_verb_debug(_LOG,
        # Enable the very verbose output.
        verbose=True)

    _LOG.verb_debug(...)
    ```
    """
    hdbg.dassert_isinstance(logger, logging.Logger)

    def _verb_debug(*args: Any, **kwargs: Any) -> None:
        if verbose:
            logger.debug(*args, **kwargs)

    return _verb_debug


# #############################################################################


def type_to_string(type_as_str: str) -> str:
    """
    Return a short string representing the type of an object, e.g.,
    "dataflow.Node" (instead of "class <'dataflow.Node'>")
    """
    if isinstance(type_as_str, type):
        type_as_str = str(type_as_str)
    hdbg.dassert_isinstance(type_as_str, str)
    # Remove the extra string from:
    #   <class 'dataflow.Zscore'>
    prefix = "<class '"
    hdbg.dassert(type_as_str.startswith(prefix), type_as_str)
    suffix = "'>"
    hdbg.dassert(type_as_str.endswith(suffix), type_as_str)
    type_as_str = type_as_str[len(prefix) : -len(suffix)]
    return type_as_str


def type_obj_to_str(obj: Any) -> str:
    ret = f"({type(obj)}) {obj}"
    return ret


# #############################################################################


def format_list(
    list_: List[Any],
    sep: str = " ",
    max_n: Optional[int] = None,
    tag: Optional[str] = None,
) -> str:
    # sep = ", "
    if max_n is None:
        max_n = 10
    max_n = cast(int, max_n)
    hdbg.dassert_lte(1, max_n)
    n = len(list_)
    txt = ""
    if tag is not None:
        txt += f"{tag}: "
    txt += f"({n}) "
    if n < max_n:
        txt += sep.join(map(str, list_))
    else:
        num_elems = int(max_n / 2)
        hdbg.dassert_lte(1, num_elems)
        txt += sep.join(map(str, list_[:num_elems]))
        txt += " ... "
        # pylint: disable=invalid-unary-operand-type
        txt += sep.join(map(str, list_[-num_elems:]))
    return txt


# TODO(gp): Use format_list().
def list_to_str(
    list_: List,
    tag: str = "",
    sort: bool = False,
    axis: int = 0,
    to_string: bool = False,
) -> str:
    """
    Print list / index horizontally or vertically.
    """
    # TODO(gp): Fix this.
    _ = to_string
    txt = ""
    if axis == 0:
        if list_ is None:
            txt += f"{tag}: (0) None\n"
        else:
            # hdbg.dassert_in(type(l), (list, pd.Index, pd.Int64Index))
            vals = list(map(str, list_))
            if sort:
                vals = sorted(vals)
            txt += f"{tag}: ({len(list_)}) {' '.join(vals)}\n"
    elif axis == 1:
        txt += f"{tag} ({len(list_)}):\n"
        vals = list(map(str, list_))
        if sort:
            vals = sorted(vals)
        txt += "\n".join(vals) + "\n"
    else:
        raise ValueError(f"Invalid axis='{axis}'")
    return txt


def set_diff_to_str(
    obj1: Iterable,
    obj2: Iterable,
    obj1_name: str = "obj1",
    obj2_name: str = "obj2",
    sep_char: str = " ",
    add_space: bool = False,
) -> str:
    """
    Compute the difference between two sequence of data.

    :param sep_char: print the objects using `sep_char` as separating char
    :param add_space: add empty lines to make the output more readable
    """

    def _to_string(obj: Iterable) -> str:
        obj = sorted(list(obj))
        if sep_char == "\n":
            txt = indent("\n" + sep_char.join(map(str, obj)))
        else:
            txt = sep_char.join(map(str, obj))
        return txt

    res: List[str] = []
    # obj1.
    obj1 = set(obj1)
    hdbg.dassert_lte(1, len(obj1))
    res.append(f"* {obj1_name}: ({len(obj1)}) {_to_string(obj1)}")
    if add_space:
        res.append("")
    # obj2.
    obj2 = set(obj2)
    hdbg.dassert_lte(1, len(obj2))
    res.append(f"* {obj2_name}: ({len(obj2)}) {_to_string(obj2)}")
    if add_space:
        res.append("")
    # obj1 intersect obj2.
    intersection = obj1.intersection(obj2)
    res.append(f"* intersect=({len(intersection)}) {_to_string(intersection)}")
    if add_space:
        res.append("")
    # obj1 - obj2.
    diff = obj1 - obj2
    res.append(f"* {obj1_name}-{obj2_name}=({len(diff)}) {_to_string(diff)}")
    if add_space:
        res.append("")
    # obj2 - obj1.
    diff = obj2 - obj1
    res.append(f"* {obj2_name}-{obj1_name}=({len(diff)}) {_to_string(diff)}")
    if add_space:
        res.append("")
    #
    res = "\n".join(res)
    return res


def obj_to_str(
    obj: Any,
    attr_mode: str = "__dict__",
    print_type: bool = False,
    callable_mode: str = "skip",
    private_mode: str = "skip_dunder",
) -> str:
    """
    Print attributes of an object.

    :param using_dict: use `__dict__` instead of `dir`
    :param print_type: print the type of the attribute
    :param callable_mode: how to handle attributes that are callable (i.e.,
        methods)
        - skip: skip the methods
        - only: print only the methods
        - all: print variables and callable
    """

    def _to_skip_callable(attr: Any, callable_mode: str) -> bool:
        hdbg.dassert_in(callable_mode, ("skip", "only", "all"))
        is_callable = callable(attr)
        skip = False
        if callable_mode == "skip" and is_callable:
            skip = True
        if callable_mode == "only" and not is_callable:
            skip = True
        return skip

    def _to_skip_private(name: str, private_mode: str) -> bool:
        hdbg.dassert_in(
            private_mode,
            ("skip_dunder", "only_dunder", "skip_private", "only_private", "all"),
        )
        is_dunder = name.startswith("__") and name.endswith("__")
        is_private = not is_dunder and name.startswith("_")
        skip = False
        if private_mode == "skip_dunder" and is_dunder:
            skip = True
        if private_mode == "only_dunder" and not is_dunder:
            skip = True
        if private_mode == "skip_private" and is_private:
            skip = True
        if private_mode == "only_private" and not is_private:
            skip = True
        return skip

    def _to_str(attr: Any, print_type: bool) -> str:
        if print_type:
            out = f"{v}= ({type(attr)}) {str(attr)}"
        else:
            out = f"{v}= {str(attr)}"
        return out

    ret = []
    if attr_mode == "__dict__":
        for v in sorted(obj.__dict__):
            attr = obj.__dict__[v]
            # Handle dunder / private methods.
            skip = _to_skip_private(v, private_mode)
            if skip:
                continue
            # Handle callable methods.
            skip = _to_skip_callable(attr, callable_mode)
            if skip:
                continue
            #
            out = _to_str(attr, print_type)
            ret.append(out)
    elif attr_mode == "dir":
        for v in dir(obj):
            attr = getattr(obj, v)
            # Handle dunder / private methods.
            skip = _to_skip_private(v, private_mode)
            if skip:
                continue
            # Handle callable methods.
            skip = _to_skip_callable(attr, callable_mode)
            if skip:
                continue
            #
            out = _to_str(attr, print_type)
            ret.append(out)
    else:
        hdbg.dassert(f"Invalid attr_mode='{attr_mode}'")
    return "\n".join(ret)


def remove_non_printable_chars(txt: str) -> str:
    # From https://stackoverflow.com/questions/14693701
    # 7-bit and 8-bit C1 ANSI sequences
    ansi_escape = re.compile(
        r"""
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI, followed by a control sequence
            \[
            [0-?]*  # Parameter bytes
            [ -/]*  # Intermediate bytes
            [@-~]   # Final byte
        )
    """,
        re.VERBOSE,
    )
    txt = ansi_escape.sub("", txt)
    return txt


# TODO(gp): Maybe move to helpers/hpython.py since it's not about printing.
def sort_dictionary(dict_: Dict) -> Dict:
    """
    Sort a dictionary recursively using nested OrderedDict.
    """
    import collections

    res = collections.OrderedDict()
    for k, v in sorted(dict_.items()):
        if isinstance(v, dict):
            res[k] = sort_dictionary(v)
        else:
            res[k] = v
    return res


def to_pretty_str(obj: Any) -> str:
    if isinstance(obj, dict):
        import pprint

        res = pprint.pformat(obj)
        # import json
        # res = json.dumps(obj, indent=4, sort_keys=True)
    else:
        res = str(obj)
    return res


def filter_text(regex: str, txt: str) -> str:
    """
    Remove lines in `txt` that match the regex `regex`.
    """
    _LOG.debug("Filtering with '%s'", regex)
    if regex is None:
        return txt
    txt_out = []
    txt_as_arr = txt.split("\n")
    for line_ in txt_as_arr:
        if re.search(regex, line_):
            _LOG.debug("Skipping line='%s'", line_)
            continue
        txt_out.append(line_)
    # We can only remove lines.
    hdbg.dassert_lte(
        len(txt_out),
        len(txt_as_arr),
        "txt_out=\n'''%s'''\ntxt=\n'''%s'''",
        "\n".join(txt_out),
        "\n".join(txt_as_arr),
    )
    txt = "\n".join(txt_out)
    return txt


# #############################################################################
# Notebook output
# #############################################################################

# TODO(gp): Move to explore.py or notebook.py


def config_notebook(sns_set: bool = True) -> None:
    # Matplotlib.
    import matplotlib.pyplot as plt

    # plt.rcParams
    plt.rcParams["figure.figsize"] = (20, 5)
    plt.rcParams["legend.fontsize"] = 14
    plt.rcParams["font.size"] = 14
    plt.rcParams["image.cmap"] = "rainbow"

    if False:
        # Tweak the size of the plots to make it more readable when embedded in
        # documents or presentations.
        # font = {'family' : 'normal',
        #         #'weight' : 'bold',
        #         'size'   : 32}
        # matplotlib.rc('font', **font)
        scale = 3
        small_size = 8 * scale
        medium_size = 10 * scale
        bigger_size = 12 * scale
        # Default text sizes.
        plt.rc("font", size=small_size)
        # Fontsize of the axes title.
        plt.rc("axes", titlesize=small_size)
        # Fontsize of the x and y labels.
        plt.rc("axes", labelsize=medium_size)
        # Fontsize of the tick labels.
        plt.rc("xtick", labelsize=small_size)
        # Fontsize of the tick labels.
        plt.rc("ytick", labelsize=small_size)
        # Legend fontsize.
        plt.rc("legend", fontsize=small_size)
        # Fontsize of the figure title.
        plt.rc("figure", titlesize=bigger_size)

    # Seaborn.
    import seaborn as sns

    if sns_set:
        sns.set()

    # Pandas.
    import pandas as pd

    pd.set_option("display.max_rows", 500)
    pd.set_option("display.max_columns", 500)
    pd.set_option("display.width", 1000)

    # Warnings.
    import helpers.hwarnings as hwarnin

    # Force the linter to keep this import.
    _ = hwarnin
