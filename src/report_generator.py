from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from datetime import datetime
import os

def generate_pdf_report(result: dict, output_dir: str = "reports/generated") -> str:
    """Génère un rapport PDF institutionnel."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tickers = "_".join(result["tickers"][:2]) if result.get("tickers") else "no_assets"
    filename = f"{output_dir}/report_{tickers}_{timestamp}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=A4,
                           rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    
    # Styles custom
    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  fontSize=20, textColor=HexColor('#1a1a2e'),
                                  spaceAfter=6)
    
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                     fontSize=11, textColor=HexColor('#666666'),
                                     spaceAfter=20)
    
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'],
                                    fontSize=13, textColor=HexColor('#1a1a2e'),
                                    spaceBefore=16, spaceAfter=8,
                                    borderPad=4)
    
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=9, leading=14,
                                 textColor=HexColor('#333333'))
    
    story = []
    
    # Header
    story.append(Paragraph("AI Quant Research Assistant", title_style))
    story.append(Paragraph(
        f"Investment Analysis Report — {datetime.now().strftime('%B %d, %Y')}",
        subtitle_style
    ))
    
    # Query
    story.append(Paragraph("Research Question", heading_style))
    story.append(Paragraph(result["query"], body_style))
    story.append(Spacer(1, 12))
    
    # Metrics table
    story.append(Paragraph("Key Metrics", heading_style))
    metrics_data = [
        ["Metric", "Value"],
        ["Tickers Analyzed", ", ".join(result["tickers"])],
        ["Expected Return", f"{result['expected_return']}%"],
        ["Expected Volatility", f"{result['expected_volatility']}%"],
        ["Sharpe Ratio", str(result["expected_sharpe"])],
    ]
    
    table = Table(metrics_data, colWidths=[8*cm, 8*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#f5f5f5'), white]),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    clean_summary = result["executive_summary"].replace("**", "").replace("*", "")
    for line in clean_summary.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 4))
    
    # Market Analysis
    story.append(Paragraph("Market Analysis", heading_style))
    clean_market = result["market_analysis"].replace("**", "").replace("*", "")
    for line in clean_market.split("\n")[:40]:
        if line.strip():
            story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 3))
    
    # Footer
    story.append(Spacer(1, 20))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
                                   fontSize=7, textColor=HexColor('#999999'))
    tickers_footer = ", ".join(result["tickers"]) if result.get("tickers") else "N/A"
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | "
        f"Data source: Yahoo Finance (yfinance) | Tickers: {tickers_footer}",
        footer_style
    ))
    story.append(Paragraph(
        "This output is for research purposes only and does not constitute financial advice.",
        footer_style
    ))
    
    doc.build(story)
    print(f"✅ PDF généré : {filename}")
    return filename