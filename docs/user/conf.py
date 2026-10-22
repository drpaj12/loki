"""Sphinx configuration of the Loki III user manual.

Build: ``sphinx-build -W -b html docs/user build/docs`` (CI job ``docs``). Every command and file
name in the pages was checked against loki/cli.py, loki/bench.py, docs/runbook-l0.md and the L0
spec. The pages need no Loki, Loki or Odin III install to build.
"""

project = "Loki III"
author = "Loki III contributors"
copyright = "Loki III contributors"

extensions = ["myst_parser"]
source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build"]
myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3
html_theme = "alabaster"

# Shared Yggdrasil III look: the "Manuals" block (hub link on top, links to every manual) leads
# the sidebar on every page. Keep _templates/manuals.html identical across the four manuals.
templates_path = ["_templates"]
html_sidebars = {
    "**": ["manuals.html", "about.html", "navigation.html", "relations.html", "searchbox.html"],
}
