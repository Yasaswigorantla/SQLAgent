from graphviz import Digraph


def generate_er(schema, relationships):
    dot = Digraph("ER")
    dot.attr(rankdir="TB")
    dot.attr("node", shape="record")

    for table in schema:
        attributes = []
        for attribute in table["attributes"]:
            if isinstance(attribute, dict):
                name = attribute.get("name", "")
                markers = []

                if attribute.get("primary_key") or attribute.get("part_of_composite_pk"):
                    markers.append("PK")
                if attribute.get("foreign_key"):
                    markers.append("FK")

                marker_text = f" ({', '.join(markers)})" if markers else ""
                attributes.append(f"{name}{marker_text}")
            else:
                attributes.append(str(attribute))

        label = "{" + table["name"] + "|" + "\\l".join(attributes) + "\\l}"
        dot.node(table["name"], label)

    for rel in relationships:
        dot.edge(rel["from"], rel["to"], label=rel["type"])

    dot.render("er_diagram", format="png", cleanup=True)
    return "er_diagram.png"
