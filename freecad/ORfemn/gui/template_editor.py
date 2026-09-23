"""Template editor: create and edit the keyword templates of the keyword editor."""

import copy
import os

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

from .. import kfile_format


def user_templates_path():
    """Path of the user's own templates file (overrides the shipped templates.json)."""
    return os.path.join(FreeCAD.getUserAppDataDir(), "ORfemn", "templates.json")


def load_active_templates():
    """Load the user's templates if they exist, otherwise the shipped defaults."""
    path = user_templates_path()
    if os.path.exists(path):
        try:
            return kfile_format.load_templates(path)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Could not read {path}, using default templates: {e}\n")
    return kfile_format.load_templates()


def load_keyword_definitions():
    """Return {keyword as written in a deck: card definitions} from the keyword database."""
    path = os.path.join(os.path.dirname(kfile_format.__file__), "keywords_with_parameters.json")
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return {(kw.get("keyword") or kw["name"]): kw.get("parameters") or []
                    for kw in json.load(f) if kw.get("name")}
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Template editor: could not load keyword database: {e}\n")
        return {}


def _button_row(*buttons):
    layout = QtWidgets.QHBoxLayout()
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch()
    return layout


class TemplateEditorDialog(QtWidgets.QDialog):
    """Dialog for creating, editing, deleting and reordering keyword templates."""

    templates_saved = QtCore.Signal()

    PARAM_COLUMNS = ["Name", "Value", "Card", "Description"]

    def __init__(self, parent=None):
        super(TemplateEditorDialog, self).__init__(parent)
        self.setWindowTitle("Template Editor")
        self.setMinimumSize(1100, 700)
        self.setModal(False)

        # Edited copy of the templates; only written to disk on Save.
        self.templates = copy.deepcopy(load_active_templates())
        self.keyword_definitions = load_keyword_definitions()
        self.dirty = False
        self._loading = False

        self.setup_ui()
        self.reload_template_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        # --- Templates -------------------------------------------------
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.addWidget(QtWidgets.QLabel("<b>Templates</b>"))
        self.template_list = QtWidgets.QListWidget()
        self.template_list.currentRowChanged.connect(self.on_template_selected)
        left_layout.addWidget(self.template_list)

        self.new_template_button = QtWidgets.QPushButton("New")
        self.new_template_button.clicked.connect(self.new_template)
        self.duplicate_template_button = QtWidgets.QPushButton("Duplicate")
        self.duplicate_template_button.clicked.connect(self.duplicate_template)
        self.delete_template_button = QtWidgets.QPushButton("Delete")
        self.delete_template_button.clicked.connect(self.delete_template)
        left_layout.addLayout(_button_row(self.new_template_button, self.duplicate_template_button,
                                          self.delete_template_button))
        self.template_up_button = QtWidgets.QPushButton("Move Up")
        self.template_up_button.clicked.connect(lambda: self.move_template(-1))
        self.template_down_button = QtWidgets.QPushButton("Move Down")
        self.template_down_button.clicked.connect(lambda: self.move_template(1))
        left_layout.addLayout(_button_row(self.template_up_button, self.template_down_button))
        splitter.addWidget(left)

        # --- Template details -----------------------------------------
        self.detail_panel = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(self.detail_panel)

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.textEdited.connect(self.on_template_fields_changed)
        form.addRow("Name:", self.name_edit)
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems([level.title() for level in kfile_format.TEMPLATE_LEVELS])
        self.level_combo.setToolTip("Template Mode in which the template is shown:\n"
                                    "Minimal ⊂ Basic ⊂ Full")
        self.level_combo.currentIndexChanged.connect(self.on_template_fields_changed)
        form.addRow("Level:", self.level_combo)
        self.description_edit = QtWidgets.QLineEdit()
        self.description_edit.textEdited.connect(self.on_template_fields_changed)
        form.addRow("Description:", self.description_edit)
        detail_layout.addLayout(form)

        inner = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Keywords of the template
        kw_panel = QtWidgets.QWidget()
        kw_layout = QtWidgets.QVBoxLayout(kw_panel)
        kw_layout.addWidget(QtWidgets.QLabel("<b>Keywords</b>"))
        self.keyword_list = QtWidgets.QListWidget()
        self.keyword_list.currentRowChanged.connect(self.on_keyword_selected)
        kw_layout.addWidget(self.keyword_list)
        self.add_keyword_button = QtWidgets.QPushButton("Add")
        self.add_keyword_button.clicked.connect(self.add_keyword)
        self.remove_keyword_button = QtWidgets.QPushButton("Remove")
        self.remove_keyword_button.clicked.connect(self.remove_keyword)
        kw_layout.addLayout(_button_row(self.add_keyword_button, self.remove_keyword_button))
        self.keyword_up_button = QtWidgets.QPushButton("Move Up")
        self.keyword_up_button.clicked.connect(lambda: self.move_keyword(-1))
        self.keyword_down_button = QtWidgets.QPushButton("Move Down")
        self.keyword_down_button.clicked.connect(lambda: self.move_keyword(1))
        kw_layout.addLayout(_button_row(self.keyword_up_button, self.keyword_down_button))
        inner.addWidget(kw_panel)

        # Parameters of the selected keyword
        self.param_panel = QtWidgets.QWidget()
        param_layout = QtWidgets.QVBoxLayout(self.param_panel)
        kw_form = QtWidgets.QFormLayout()
        self.keyword_name_edit = QtWidgets.QLineEdit()
        self.keyword_name_edit.setPlaceholderText("*KEYWORD_NAME")
        completer = QtWidgets.QCompleter(sorted(self.keyword_definitions), self.keyword_name_edit)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.keyword_name_edit.setCompleter(completer)
        self.keyword_name_edit.textChanged.connect(self.on_keyword_name_changed)
        kw_form.addRow("Keyword:", self.keyword_name_edit)
        param_layout.addLayout(kw_form)

        self.param_table = QtWidgets.QTableWidget(0, len(self.PARAM_COLUMNS))
        self.param_table.setHorizontalHeaderLabels(self.PARAM_COLUMNS)
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.setToolTip("One row per field, in card order. 'Card' starts at 1.\n"
                                    "An empty value keeps a field at its default but holds its position.")
        self.param_table.itemChanged.connect(self.on_param_table_changed)
        param_layout.addWidget(self.param_table)

        self.add_param_button = QtWidgets.QPushButton("Add Field")
        self.add_param_button.clicked.connect(self.add_parameter)
        self.remove_param_button = QtWidgets.QPushButton("Remove Field")
        self.remove_param_button.clicked.connect(self.remove_parameter)
        self.param_up_button = QtWidgets.QPushButton("Move Up")
        self.param_up_button.clicked.connect(lambda: self.move_parameter(-1))
        self.param_down_button = QtWidgets.QPushButton("Move Down")
        self.param_down_button.clicked.connect(lambda: self.move_parameter(1))
        self.fill_fields_button = QtWidgets.QPushButton("Insert Fields from Database")
        self.fill_fields_button.setToolTip("Append a row for every field of this keyword's required cards as "
                                           "listed in the keyword database, prefilled with documented defaults")
        self.fill_fields_button.clicked.connect(self.insert_fields_from_database)
        param_layout.addLayout(_button_row(self.add_param_button, self.remove_param_button,
                                           self.param_up_button, self.param_down_button,
                                           self.fill_fields_button))
        inner.addWidget(self.param_panel)
        inner.setSizes([250, 550])
        detail_layout.addWidget(inner, 3)

        detail_layout.addWidget(QtWidgets.QLabel("<b>Preview</b>"))
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        detail_layout.addWidget(self.preview, 2)

        splitter.addWidget(self.detail_panel)
        splitter.setSizes([250, 850])

        # --- Bottom buttons -------------------------------------------
        self.reset_button = QtWidgets.QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.reset_button)
        bottom.addStretch()
        self.status_label = QtWidgets.QLabel()
        bottom.addWidget(self.status_label)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.close_button)
        layout.addLayout(bottom)

        self.update_status()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def template_ids(self):
        return list(self.templates)

    def current_template_id(self):
        row = self.template_list.currentRow()
        ids = self.template_ids()
        return ids[row] if 0 <= row < len(ids) else None

    def current_template(self):
        template_id = self.current_template_id()
        return self.templates[template_id] if template_id else None

    def current_keyword(self):
        template = self.current_template()
        row = self.keyword_list.currentRow()
        if template and 0 <= row < len(template.get("keywords", [])):
            return template["keywords"][row]
        return None

    def mark_dirty(self):
        if not self._loading:
            self.dirty = True
            self.update_status()
            self.update_preview()

    def update_status(self):
        path = user_templates_path()
        source = "your templates" if os.path.exists(path) else "default templates"
        self.status_label.setText(("Unsaved changes — " if self.dirty else "") + f"editing {source}")
        self.save_button.setEnabled(self.dirty)

    def _reorder_templates(self, ids):
        self.templates = {template_id: self.templates[template_id] for template_id in ids}

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def reload_template_list(self, select_row=0):
        self._loading = True
        self.template_list.clear()
        for template_id, template in self.templates.items():
            self.template_list.addItem(template.get("name") or template_id)
        self._loading = False
        if self.templates:
            self.template_list.setCurrentRow(max(0, min(select_row, len(self.templates) - 1)))
        self.on_template_selected(self.template_list.currentRow())

    def on_template_selected(self, row):
        if self._loading:
            return
        template = self.current_template()
        self.detail_panel.setEnabled(template is not None)
        for button in (self.duplicate_template_button, self.delete_template_button,
                       self.template_up_button, self.template_down_button):
            button.setEnabled(template is not None)

        self._loading = True
        self.name_edit.setText(template.get("name", "") if template else "")
        level = template.get("level", "full") if template else "full"
        self.level_combo.setCurrentIndex(
            kfile_format.TEMPLATE_LEVELS.index(level) if level in kfile_format.TEMPLATE_LEVELS else 2)
        self.description_edit.setText(template.get("description", "") if template else "")
        self.keyword_list.clear()
        for kw in (template.get("keywords", []) if template else []):
            self.keyword_list.addItem(kw.get("name", ""))
        self._loading = False

        if self.keyword_list.count():
            self.keyword_list.setCurrentRow(0)
        self.on_keyword_selected(self.keyword_list.currentRow())
        self.update_preview()

    def on_template_fields_changed(self, *_args):
        template = self.current_template()
        if self._loading or template is None:
            return
        template["name"] = self.name_edit.text()
        template["level"] = kfile_format.TEMPLATE_LEVELS[self.level_combo.currentIndex()]
        template["description"] = self.description_edit.text()
        item = self.template_list.currentItem()
        if item:
            item.setText(template["name"] or self.current_template_id())
        self.mark_dirty()

    def new_template(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Template", "Template name:")
        if not ok or not name.strip():
            return
        template_id = kfile_format.make_template_id(name, self.templates)
        # "minimal" is shown in every Template Mode, so a new template is always visible in the menu
        self.templates[template_id] = {
            "name": name.strip(), "level": "minimal", "description": "",
            "keywords": [{"name": "*CONTROL_TERMINATION", "parameters": [
                {"name": "ENDTIM", "value": "1.0", "description": "Termination time"}]}],
        }
        self.reload_template_list(len(self.templates) - 1)
        self.mark_dirty()

    def duplicate_template(self):
        template = self.current_template()
        if template is None:
            return
        duplicate = copy.deepcopy(template)
        duplicate["name"] = f"{template.get('name', '')} (copy)"
        template_id = kfile_format.make_template_id(duplicate["name"], self.templates)
        ids = self.template_ids()
        row = self.template_list.currentRow()
        self.templates[template_id] = duplicate
        self._reorder_templates(ids[:row + 1] + [template_id] + ids[row + 1:])
        self.reload_template_list(row + 1)
        self.mark_dirty()

    def delete_template(self):
        template_id = self.current_template_id()
        if template_id is None:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Template",
            f"Delete template '{self.templates[template_id].get('name', template_id)}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply != QtWidgets.QMessageBox.Yes:
            return
        row = self.template_list.currentRow()
        del self.templates[template_id]
        self.reload_template_list(row)
        self.mark_dirty()

    def move_template(self, offset):
        ids = self.template_ids()
        row = self.template_list.currentRow()
        target = row + offset
        if not (0 <= row < len(ids) and 0 <= target < len(ids)):
            return
        ids[row], ids[target] = ids[target], ids[row]
        self._reorder_templates(ids)
        self.reload_template_list(target)
        self.mark_dirty()

    # ------------------------------------------------------------------
    # Keywords
    # ------------------------------------------------------------------

    def on_keyword_selected(self, row):
        if self._loading:
            return
        kw = self.current_keyword()
        self.param_panel.setEnabled(kw is not None)
        for button in (self.remove_keyword_button, self.keyword_up_button, self.keyword_down_button):
            button.setEnabled(kw is not None)

        self._loading = True
        self.keyword_name_edit.setText(kw.get("name", "") if kw else "")
        self.param_table.setRowCount(0)
        for param in (kw.get("parameters", []) if kw else []):
            self._append_param_row(param)
        self._loading = False
        self.update_fill_button()

    def _append_param_row(self, param):
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        try:
            card = str(int(param.get("card", 0)) + 1)
        except (TypeError, ValueError):
            card = str(param.get("card"))  # invalid; shown as typed so it can be fixed
        values = [param.get("name", ""), param.get("value", param.get("field_0", "")),
                  card, param.get("description", "")]
        for col, value in enumerate(values):
            self.param_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

    def _rebuild_keyword_list_text(self):
        template = self.current_template()
        for row, kw in enumerate(template.get("keywords", []) if template else []):
            item = self.keyword_list.item(row)
            if item:
                item.setText(kw.get("name", ""))

    def on_keyword_name_changed(self, text):
        kw = self.current_keyword()
        if self._loading or kw is None:
            return
        kw["name"] = text.strip().upper()
        self._rebuild_keyword_list_text()
        self.update_fill_button()
        self.mark_dirty()

    def update_fill_button(self):
        kw = self.current_keyword()
        self.fill_fields_button.setEnabled(bool(kw and self.keyword_definitions.get(kw.get("name", ""))))

    def add_keyword(self):
        template = self.current_template()
        if template is None:
            return
        row = self.keyword_list.currentRow() + 1
        template.setdefault("keywords", []).insert(row, {"name": "*", "parameters": []})
        self.on_template_selected(self.template_list.currentRow())
        self.keyword_list.setCurrentRow(row)
        self.keyword_name_edit.setFocus()
        self.keyword_name_edit.setCursorPosition(1)
        self.mark_dirty()

    def remove_keyword(self):
        template = self.current_template()
        row = self.keyword_list.currentRow()
        if template is None or not 0 <= row < len(template.get("keywords", [])):
            return
        del template["keywords"][row]
        self.on_template_selected(self.template_list.currentRow())
        self.keyword_list.setCurrentRow(min(row, self.keyword_list.count() - 1))
        self.mark_dirty()

    def move_keyword(self, offset):
        template = self.current_template()
        row = self.keyword_list.currentRow()
        keywords = template.get("keywords", []) if template else []
        target = row + offset
        if not (0 <= row < len(keywords) and 0 <= target < len(keywords)):
            return
        keywords[row], keywords[target] = keywords[target], keywords[row]
        self.on_template_selected(self.template_list.currentRow())
        self.keyword_list.setCurrentRow(target)
        self.mark_dirty()

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def _params_from_table(self):
        params = []
        for row in range(self.param_table.rowCount()):
            def text(col):
                item = self.param_table.item(row, col)
                return item.text().strip() if item else ""
            param = {"name": text(0), "value": text(1), "description": text(3)}
            try:
                card = int(text(2) or 1) - 1
            except ValueError:
                card = text(2)  # left as-is so validation reports it
            if card != 0:
                param["card"] = card
            params.append(param)
        return params

    def on_param_table_changed(self, _item=None):
        kw = self.current_keyword()
        if self._loading or kw is None:
            return
        kw["parameters"] = self._params_from_table()
        self.mark_dirty()

    def add_parameter(self):
        kw = self.current_keyword()
        if kw is None:
            return
        row = self.param_table.currentRow()
        card = 0
        neighbour = kw["parameters"][row] if 0 <= row < len(kw["parameters"]) else \
            (kw["parameters"][-1] if kw["parameters"] else {})
        try:
            card = int(neighbour.get("card", 0))
        except (TypeError, ValueError):
            pass
        insert_at = row + 1 if row >= 0 else len(kw["parameters"])
        kw.setdefault("parameters", []).insert(insert_at, {"name": "", "value": "", "card": card,
                                                           "description": ""})
        if card == 0:
            del kw["parameters"][insert_at]["card"]
        self.on_keyword_selected(self.keyword_list.currentRow())
        self.param_table.setCurrentCell(insert_at, 0)
        self.param_table.editItem(self.param_table.item(insert_at, 0))
        self.mark_dirty()

    def remove_parameter(self):
        kw = self.current_keyword()
        rows = sorted({index.row() for index in self.param_table.selectedIndexes()}, reverse=True)
        if kw is None or not rows:
            return
        for row in rows:
            del kw["parameters"][row]
        self.on_keyword_selected(self.keyword_list.currentRow())
        self.mark_dirty()

    def move_parameter(self, offset):
        kw = self.current_keyword()
        row = self.param_table.currentRow()
        params = kw.get("parameters", []) if kw else []
        target = row + offset
        if not (0 <= row < len(params) and 0 <= target < len(params)):
            return
        params[row], params[target] = params[target], params[row]
        column = self.param_table.currentColumn()
        self.on_keyword_selected(self.keyword_list.currentRow())
        self.param_table.setCurrentCell(target, max(column, 0))
        self.mark_dirty()

    def insert_fields_from_database(self):
        """Append one row per field of the keyword's required cards (up to the last named field).

        Optional cards (e.g. _INERTIA) are left out; they belong to a different keyword variant.
        """
        kw = self.current_keyword()
        cards = self.keyword_definitions.get(kw.get("name", "")) if kw else None
        if not cards:
            return
        for card_index, card in enumerate(c for c in cards if not c.get("optional")):
            names = [card.get(f"field_{i}", "") for i in range(kfile_format.FIELDS_PER_CARD)]
            while names and not names[-1]:
                names.pop()
            defaults = card.get("defaults", {})
            field_help = card.get("field_help", {})
            for i, name in enumerate(names):
                param = {"name": name, "value": defaults.get(f"field_{i}", ""),
                         "description": field_help.get(f"field_{i}", "")}
                if card_index:
                    param["card"] = card_index
                kw["parameters"].append(param)
        self.on_keyword_selected(self.keyword_list.currentRow())
        self.mark_dirty()

    # ------------------------------------------------------------------
    # Preview, save, reset, close
    # ------------------------------------------------------------------

    def update_preview(self):
        template = self.current_template()
        if template is None:
            self.preview.setPlainText("")
            return
        try:
            entries = [(kw.get("name", ""), kfile_format.template_keyword_text(kw))
                       for kw in template.get("keywords", [])]
            self.preview.setPlainText(kfile_format.build_k_file(entries, title=template.get("name")))
        except (TypeError, ValueError) as e:
            self.preview.setPlainText(f"Cannot build preview: {e}")

    def save(self):
        errors = kfile_format.validate_templates(self.templates)
        if errors:
            QtWidgets.QMessageBox.warning(self, "Cannot Save Templates",
                                          "Please fix these problems first:\n\n• " + "\n• ".join(errors[:20]))
            return False
        path = user_templates_path()
        try:
            kfile_format.save_templates(self.templates, path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save templates:\n{e}")
            return False
        self.dirty = False
        self.update_status()
        self.templates_saved.emit()
        FreeCAD.Console.PrintMessage(f"Templates saved to {path}\n")
        return True

    def reset_to_defaults(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Reset to Defaults",
            "Discard your templates (including saved ones) and restore the default templates?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply != QtWidgets.QMessageBox.Yes:
            return
        path = user_templates_path()
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Reset Error", f"Could not remove {path}:\n{e}")
            return
        self.templates = copy.deepcopy(kfile_format.load_templates())
        self.dirty = False
        self.reload_template_list()
        self.update_status()
        self.templates_saved.emit()

    def reject(self):
        # Escape key: go through closeEvent so unsaved changes are not lost
        self.close()

    def closeEvent(self, event):
        if self.dirty:
            reply = QtWidgets.QMessageBox.question(
                self, "Unsaved Changes", "Save changes to the templates before closing?",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
            if reply == QtWidgets.QMessageBox.Cancel or (reply == QtWidgets.QMessageBox.Save and not self.save()):
                event.ignore()
                return
        event.accept()
