"""诗词：逻辑在本包；本 Blueprint 仅挂载本功能模板目录。"""

from flask import Blueprint

poems_bp = Blueprint("poems_ui", __name__, template_folder="templates")
