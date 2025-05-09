"""Helper for writing new source code based on new Vendor Configuration"""

import astor
import libcst as cst
from black import FileMode, format_str


class OrmClassFormatter(cst.CSTTransformer):
    """Formats class definitions with proper spacing between sections"""

    def _get_statement_type(self, stmt: cst.CSTNode) -> str:
        """Determine the type of given statement"""
        if isinstance(stmt, cst.SimpleStatementLine):  # noqa: SIM102
            if len(stmt.body) == 1:  # noqa: SIM102
                if isinstance(stmt.body[0], cst.Assign):
                    if isinstance(stmt.body[0].targets[0], cst.Name):
                        name = stmt.body[0].targets[0].value
                        if name.startswith("__"):
                            return "dunder"
                    value = stmt.body[0].value
                    if isinstance(value, cst.Call):
                        func_name = str(value.func.value)
                        if "Column" in func_name:
                            return "column"
                        if "relationship" in func_name:
                            return "relationship"
        return "other"

    def leave_ClassDef(  # noqa: N802
        self,
        original_node: cst.ClassDef,  # noqa: ARG002
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """Update Class Definition"""
        # Group statements by type
        body = []
        current_group = []
        last_type = None

        for stmt in updated_node.body.body:
            curr_type = self._get_statement_type(stmt)

            if last_type is not None and curr_type != last_type:
                body.extend(current_group)
                body.append(cst.EmptyLine())
                current_group = []

            current_group.append(stmt)
            last_type = curr_type

        if current_group:
            body.extend(current_group)

        return updated_node.with_changes(body=updated_node.body.with_changes(body=body))

    @classmethod
    def format(cls, tree: cst.Module) -> cst.Module:
        """Convert back to source, use black to format"""
        source = format_str(
            astor.to_source(tree),
            mode=FileMode(line_length=120, magic_trailing_comma=True),
        )

        # Parse with LibCST for formatting
        module = cst.parse_module(source)
        return module.visit(cls())
