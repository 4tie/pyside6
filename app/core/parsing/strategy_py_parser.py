"""
AST-based parser for Freqtrade strategy .py files.

Extracts parameter definitions (IntParameter, DecimalParameter,
CategoricalParameter, BooleanParameter) and strategy metadata
(class name, timeframe, minimal_roi, stoploss, trailing settings)
from a strategy source file using Python's ast module.

V1 Scope Limitation
-------------------
Only parameters declared **directly in the strategy class body** are
extracted.  Parameters inherited from a base class (e.g.
``class MyStrategy(BaseStrategy):``) are not visible to a single-file
AST parse — the parser does not traverse the filesystem to locate and
parse parent classes.  If a strategy relies on inherited parameters the
user will see an empty parameter table and should define the parameters
locally or configure them manually.

The UI must surface this limitation as a tooltip on the parameter table.

Architecture boundary: NO PySide6 imports in this module.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.models.optimizer_models import ParamDef, ParamType, StrategyParams
from app.core.utils.app_logger import get_logger

_log = get_logger("parsing.strategy_py_parser")

_PARAM_CLASSES: Dict[str, ParamType] = {
    "IntParameter":         ParamType.INT,
    "DecimalParameter":     ParamType.DECIMAL,
    "CategoricalParameter": ParamType.CATEGORICAL,
    "BooleanParameter":     ParamType.BOOLEAN,
}


def _get_func_name(node: ast.Call) -> str:
    """Return the bare function/class name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _eval_constant(node: ast.expr) -> Any:
    """
    Safely evaluate a simple AST node to a Python value.

    Handles:
    - ast.Constant  → the literal value
    - ast.UnaryOp(USub, Constant)  → negative number
    - ast.List / ast.Tuple  → list of evaluated elements
    - anything else → None
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _eval_constant(node.operand)
        if isinstance(inner, (int, float)):
            return -inner
    if isinstance(node, (ast.List, ast.Tuple)):
        result = []
        for elt in node.elts:
            val = _eval_constant(elt)
            result.append(val)
        return result
    return None


class _ParamVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts Freqtrade parameter declarations from a
    strategy class body.

    After visiting, results are available in:
    - ``params``          : Dict[str, ParamDef]
    - ``strategy_class``  : str
    - ``timeframe``       : str
    - ``minimal_roi``     : Dict[str, float]
    - ``stoploss``        : float
    - ``trailing_stop``   : bool
    - ``trailing_stop_positive``        : Optional[float]
    - ``trailing_stop_positive_offset`` : Optional[float]
    """

    def __init__(self) -> None:
        self.params: Dict[str, ParamDef] = {}
        self.strategy_class: str = ""
        self.timeframe: str = "5m"
        self.minimal_roi: Dict[str, float] = {}
        self.stoploss: float = -0.10
        self.trailing_stop: bool = False
        self.trailing_stop_positive: Optional[float] = None
        self.trailing_stop_positive_offset: Optional[float] = None
        self._in_strategy_class: bool = False
        self._current_space: str = "buy"

    # ------------------------------------------------------------------
    # Class-level traversal
    # ------------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit the first (outermost) class definition as the strategy class."""
        if not self._in_strategy_class:
            self._in_strategy_class = True
            self.strategy_class = node.name
            self.generic_visit(node)
            self._in_strategy_class = False
        # Do not recurse into nested classes

    # ------------------------------------------------------------------
    # Assignment-level traversal
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle simple assignments inside the strategy class body."""
        if not self._in_strategy_class:
            self.generic_visit(node)
            return

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id

            # ---- space context ----
            if name in ("buy_params", "sell_params"):
                self._current_space = "buy" if "buy" in name else "sell"
                # Extract defaults from the dict if present
                if isinstance(node.value, ast.Dict):
                    self._extract_dict_defaults(node.value, self._current_space)
                self.generic_visit(node)
                return

            # ---- strategy metadata ----
            val = _eval_constant(node.value)
            if name == "timeframe" and isinstance(val, str):
                self.timeframe = val
                return
            if name == "stoploss" and isinstance(val, (int, float)):
                self.stoploss = float(val)
                return
            if name == "trailing_stop" and isinstance(val, bool):
                self.trailing_stop = val
                return
            if name == "trailing_stop_positive" and isinstance(val, (int, float)):
                self.trailing_stop_positive = float(val)
                return
            if name == "trailing_stop_positive_offset" and isinstance(val, (int, float)):
                self.trailing_stop_positive_offset = float(val)
                return
            if name == "minimal_roi" and isinstance(node.value, ast.Dict):
                self.minimal_roi = self._extract_roi_dict(node.value)
                return

            # ---- parameter declaration ----
            if isinstance(node.value, ast.Call):
                param = self._extract_param(name, node.value)
                if param is not None:
                    self.params[name] = param
                    return

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Handle annotated assignments: buy_rsi: int = IntParameter(...)"""
        if not self._in_strategy_class:
            self.generic_visit(node)
            return
        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return
        name = node.target.id
        if node.value and isinstance(node.value, ast.Call):
            param = self._extract_param(name, node.value)
            if param is not None:
                self.params[name] = param
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_param(self, name: str, call: ast.Call) -> Optional[ParamDef]:
        """Build a ParamDef from a parameter class Call node, or None."""
        func_name = _get_func_name(call)
        if func_name not in _PARAM_CLASSES:
            return None
        param_type = _PARAM_CLASSES[func_name]

        # Collect keyword arguments
        kwargs: Dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg:
                kwargs[kw.arg] = _eval_constant(kw.value)

        # Collect positional arguments
        positional: List[Any] = [_eval_constant(a) for a in call.args]

        # Determine space
        space = kwargs.get("space", self._current_space)
        if not isinstance(space, str):
            space = self._current_space

        default = kwargs.get("default")

        if param_type in (ParamType.INT, ParamType.DECIMAL):
            low = kwargs.get("low", positional[0] if len(positional) > 0 else None)
            high = kwargs.get("high", positional[1] if len(positional) > 1 else None)
            if default is None and len(positional) > 2:
                default = positional[2]
            return ParamDef(
                name=name,
                param_type=param_type,
                default=default,
                low=float(low) if low is not None else None,
                high=float(high) if high is not None else None,
                space=space,
            )

        if param_type == ParamType.CATEGORICAL:
            categories = kwargs.get("categories", positional[0] if positional else None)
            if not isinstance(categories, list):
                categories = [categories] if categories is not None else []
            return ParamDef(
                name=name,
                param_type=param_type,
                default=default,
                categories=categories,
                space=space,
            )

        if param_type == ParamType.BOOLEAN:
            return ParamDef(
                name=name,
                param_type=param_type,
                default=default if default is not None else False,
                space=space,
            )

        return None

    def _extract_dict_defaults(self, dict_node: ast.Dict, space: str) -> None:
        """Extract default values from a buy_params / sell_params dict literal."""
        for key_node, val_node in zip(dict_node.keys, dict_node.values):
            if key_node is None:
                continue
            key = _eval_constant(key_node)
            if not isinstance(key, str):
                continue
            val = _eval_constant(val_node)
            if key in self.params:
                # Update default on existing ParamDef
                self.params[key] = self.params[key].model_copy(update={"default": val})

    def _extract_roi_dict(self, dict_node: ast.Dict) -> Dict[str, float]:
        """Extract minimal_roi dict from an AST Dict node."""
        roi: Dict[str, float] = {}
        for key_node, val_node in zip(dict_node.keys, dict_node.values):
            if key_node is None:
                continue
            key = _eval_constant(key_node)
            val = _eval_constant(val_node)
            if key is not None and val is not None:
                try:
                    roi[str(key)] = float(val)
                except (TypeError, ValueError):
                    pass
        return roi


def parse_strategy_py(path: Path) -> StrategyParams:
    """
    Parse a Freqtrade strategy ``.py`` file and return a :class:`StrategyParams`
    object containing all detected parameter definitions and strategy metadata.

    Never raises — returns a ``StrategyParams`` with empty ``buy_params`` and
    ``sell_params`` dicts if the file cannot be parsed or contains no parameters.

    Parameters
    ----------
    path:
        Absolute or relative path to the strategy ``.py`` file.

    Returns
    -------
    StrategyParams
        Parsed strategy metadata and parameter definitions.
    """
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("Cannot read strategy file %s: %s", path, exc)
        return StrategyParams(strategy_class=Path(path).stem)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        _log.warning("Syntax error in strategy file %s: %s", path, exc)
        return StrategyParams(strategy_class=Path(path).stem)

    visitor = _ParamVisitor()
    try:
        visitor.visit(tree)
    except Exception as exc:  # noqa: BLE001
        _log.warning("AST traversal error in %s: %s", path, exc)
        return StrategyParams(strategy_class=Path(path).stem)

    # Split params into buy/sell by space
    buy_params: Dict[str, ParamDef] = {}
    sell_params: Dict[str, ParamDef] = {}
    for param_name, param_def in visitor.params.items():
        if param_def.space == "sell":
            sell_params[param_name] = param_def
        else:
            buy_params[param_name] = param_def

    strategy_class = visitor.strategy_class or Path(path).stem

    return StrategyParams(
        strategy_class=strategy_class,
        timeframe=visitor.timeframe,
        minimal_roi=visitor.minimal_roi,
        stoploss=visitor.stoploss,
        trailing_stop=visitor.trailing_stop,
        trailing_stop_positive=visitor.trailing_stop_positive,
        trailing_stop_positive_offset=visitor.trailing_stop_positive_offset,
        buy_params=buy_params,
        sell_params=sell_params,
    )
