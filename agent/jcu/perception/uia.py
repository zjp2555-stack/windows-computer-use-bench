"""UIA 文本快照：把窗口的可交互控件转成编号文本列表（Jev 组合路线的"看界面"环节）。

输出形如 `@e7 [Button] "确定"` 的行，既是决策 state 的原料，也用于执行器按 @id 定位控件。
"""

from dataclasses import dataclass
from typing import List, Optional

# 只保留可交互控件，避免把整棵 UIA 树灌进 state
INTERACTIVE_ROLES = {
    "Button", "CheckBox", "RadioButton", "MenuItem", "TabItem", "ListItem",
    "Edit", "ComboBox", "Hyperlink", "TreeItem", "DataItem", "Spinner",
    "Slider", "ScrollBar", "Custom", "Document",
}


@dataclass
class Element:
    eid: str          # 如 "e7"
    role: str         # UIA control_type
    name: str         # 可访问性名称（可能为空）
    ctrl: object      # 原始 pywinauto 控件，执行器使用

    def to_line(self) -> str:
        return f'@{self.eid} [{self.role}] "{self.name}"'


def snapshot(title_re: str = ".*", scope: Optional[str] = None,
             max_elements: int = 200, process: Optional[int] = None) -> List[Element]:
    """抓取标题匹配 title_re 的第一个顶层窗口的可交互元素。

    process：按进程号直连该进程的顶层窗口（标题匹配不可靠时的兜底，
    如 UWP 应用或全量枚举很慢的桌面）。惰性匹配单个窗口，不做全量枚举。
    scope：只保留名称含该关键字的控件——复杂界面超 255 选项时的分域手段。
    max_elements：快照封顶，配合分域保证送入决策的规模可控。
    """
    from pywinauto import Desktop  # 延迟导入：无 GUI 环境也能先跑 M1 静态评测

    if process is not None:
        from pywinauto import Application

        target = Application(backend="uia").connect(process=process, timeout=15).top_window()
    else:
        spec = Desktop(backend="uia").window(title_re=title_re)
        if not spec.exists(timeout=15):
            raise RuntimeError(f"未找到标题匹配 {title_re!r} 的窗口")
        target = spec.wrapper_object()

    elements: List[Element] = []
    for idx, ctrl in enumerate(target.descendants()):
        role = ctrl.element_info.control_type or ""
        if role not in INTERACTIVE_ROLES:
            continue
        name = (ctrl.window_text() or "").strip()
        if scope and scope not in name:
            continue
        elements.append(Element(eid=f"e{idx}", role=role, name=name, ctrl=ctrl))
        if len(elements) >= max_elements:
            break
    return elements
