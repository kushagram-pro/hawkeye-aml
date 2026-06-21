import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from app.pipeline.orchestrator import last_results
from app.schemas import InvestigationGraph

router = APIRouter()


def _node_color(risk_score: float | None) -> str:
    score = risk_score or 0
    if score >= 85:
        return "#dc2626"
    if score >= 60:
        return "#ea580c"
    if score >= 30:
        return "#d97706"
    return "#2563eb"


def _render_graph_image(graph: InvestigationGraph) -> io.BytesIO | None:
    if not graph.accounts:
        return None

    g = nx.DiGraph()
    for account in graph.accounts:
        g.add_node(account.id)
    for tx in graph.transactions:
        g.add_edge(tx.from_account, tx.to_account)

    flagged_accounts = {
        account_id for pattern in graph.flagged_patterns for account_id in pattern.accounts_involved
    }
    flagged_edges = {
        (tx.from_account, tx.to_account)
        for pattern in graph.flagged_patterns
        for tx in graph.transactions
        if tx.from_account in pattern.accounts_involved and tx.to_account in pattern.accounts_involved
    }

    accounts_by_id = {a.id: a for a in graph.accounts}
    node_colors = [_node_color(accounts_by_id[n].risk_score) for n in g.nodes]
    node_sizes = [260 if n in flagged_accounts else 140 for n in g.nodes]
    edge_colors = ["#dc2626" if e in flagged_edges else "#cbd5e1" for e in g.edges]
    edge_widths = [1.8 if e in flagged_edges else 0.8 for e in g.edges]

    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=160)
    layout = nx.spring_layout(g, seed=7, k=1.4 / max(len(g.nodes) ** 0.5, 1))

    nx.draw_networkx_edges(g, layout, ax=ax, edge_color=edge_colors, width=edge_widths, arrows=False)
    nx.draw_networkx_nodes(g, layout, ax=ax, node_color=node_colors, node_size=node_sizes, linewidths=0)
    nx.draw_networkx_labels(g, layout, ax=ax, font_size=7, font_color="#0f172a")

    ax.set_axis_off()
    fig.tight_layout(pad=0.4)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", transparent=True)
    plt.close(fig)
    buffer.seek(0)
    return buffer


@router.get("/investigate/{scenario_id}/report.pdf")
def download_report(scenario_id: str):
    graph = last_results.get(scenario_id)
    if not graph:
        raise HTTPException(404, "No completed investigation for this scenario")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"HawkEye AML — Investigation Report: {scenario_id}", styles["Title"]),
        Spacer(1, 12),
    ]

    if graph.executive_summary:
        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(Paragraph(graph.executive_summary, styles["BodyText"]))
        story.append(Spacer(1, 16))

    graph_image = _render_graph_image(graph)
    if graph_image:
        story.append(Paragraph("Money Trail Graph", styles["Heading2"]))
        story.append(Image(graph_image, width=6.5 * inch, height=4.5 * inch))
        story.append(Spacer(1, 16))

    if not graph.flagged_patterns:
        story.append(Paragraph("No suspicious patterns were confirmed in this investigation.", styles["BodyText"]))

    for pattern in graph.flagged_patterns:
        story.append(
            Paragraph(
                f"{pattern.pattern_type.replace('_', ' ').title()} — Risk Score {pattern.risk_score} "
                f"({pattern.confidence} confidence)",
                styles["Heading2"],
            )
        )
        story.append(Paragraph(pattern.narrative or pattern.reasoning, styles["BodyText"]))
        story.append(Paragraph(f"Accounts involved: {', '.join(pattern.accounts_involved)}", styles["BodyText"]))

        if pattern.skeptic_challenge:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Adversarial review:", styles["Heading3"]))
            story.append(Paragraph(pattern.skeptic_challenge, styles["BodyText"]))

        if pattern.next_steps:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Recommended next steps:", styles["Heading3"]))
            for step in pattern.next_steps:
                story.append(Paragraph(f"• {step}", styles["BodyText"]))

        if pattern.similar_past_cases:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Case memory:", styles["Heading3"]))
            for note in pattern.similar_past_cases:
                story.append(Paragraph(f"• {note}", styles["BodyText"]))

        story.append(Spacer(1, 16))

    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={scenario_id}-report.pdf"},
    )
