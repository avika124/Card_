// lib/docxGenerator.js — Generate color-coded compliance DOCX (Node.js)
// Uses docx npm package
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, WidthType, ShadingType, BorderStyle } = require("docx");

const SEVERITY_BG = {
  high:   "FFCCCC",
  medium: "FFF2CC",
  low:    "E8F5E9",
  pass:   "CCFFCC",
};
const SEVERITY_COLOR = {
  high:   "C00000",
  medium: "BF8F00",
  low:    "2E7D32",
  pass:   "007000",
};

function shadedCell(text, bg, color = "000000", bold = false, size = 18) {
  return new TableCell({
    shading: { fill: bg, type: ShadingType.CLEAR },
    borders: {
      top:    { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
      left:   { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
      right:  { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
    },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold, color, size, font: "Arial" })],
    })],
  });
}

async function generateComplianceDocx(findingsResult, documentName = "Analyzed Document", originalExcerpt = "") {
  const findings = findingsResult.findings || [];
  const overall = findingsResult.overall_risk || "unknown";
  const overallColor = SEVERITY_COLOR[overall] || "000000";

  const counts = { high: 0, medium: 0, low: 0, pass: 0 };
  findings.forEach(f => { const s = f.severity || "low"; counts[s] = (counts[s] || 0) + 1; });

  const sorted = [...findings].sort((a, b) => {
    const o = { high: 0, medium: 1, low: 2, pass: 3 };
    return (o[a.severity] || 2) - (o[b.severity] || 2);
  });

  const findingRows = sorted.map((f, i) => {
    const bg = SEVERITY_BG[f.severity] || "F2F2F2";
    const sc = SEVERITY_COLOR[f.severity] || "000000";
    const children = [
      new Paragraph({ children: [new TextRun({ text: f.issue || "", bold: true, size: 16, font: "Arial" })] }),
      new Paragraph({ children: [new TextRun({ text: f.detail || "", size: 15, font: "Arial", color: "5A5A5A" })] }),
    ];
    if (f.excerpt) children.push(new Paragraph({ children: [
      new TextRun({ text: "Excerpt: ", bold: true, italic: true, size: 15, font: "Arial" }),
      new TextRun({ text: `"${f.excerpt}"`, italic: true, size: 15, font: "Arial", color: "5A5A5A" }),
    ]}));
    if (f.recommendation) children.push(new Paragraph({ children: [
      new TextRun({ text: "→ Recommendation: ", bold: true, size: 15, font: "Arial", color: "007000" }),
      new TextRun({ text: f.recommendation, size: 15, font: "Arial", color: "007000" }),
    ]}));

    return new TableRow({ children: [
      shadedCell(String(i + 1), bg, "000000", true, 16),
      new TableCell({
        shading: { fill: bg, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: (f.severity || "").toUpperCase(), bold: true, color: sc, size: 16, font: "Arial" })] })],
      }),
      shadedCell(f.regulation || "", bg, "000000", false, 16),
      new TableCell({
        shading: { fill: bg, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children,
      }),
    ]});
  });

  const doc = new Document({
    sections: [{
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        new Paragraph({ children: [new TextRun({ text: "CREDIT CARD COMPLIANCE CHECKER", bold: true, color: "1C2D4F", size: 24, font: "Arial" })] }),
        new Paragraph({ children: [new TextRun({ text: `Document: ${documentName}`, size: 20, color: "5A5A5A", font: "Arial", italics: true })] }),
        new Paragraph({ children: [new TextRun({ text: `Overall Risk: ${overall.toUpperCase()}`, bold: true, color: overallColor, size: 26, font: "Arial" })] }),
        new Paragraph({ children: [new TextRun({ text: findingsResult.summary || "", size: 20, font: "Arial" })] }),
        new Paragraph({ children: [new TextRun({ text: "" })] }),

        // Stats table
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2340, 2340, 2340, 2340],
          rows: [
            new TableRow({ children: [
              shadedCell(`${counts.high} HIGH`, "FFCCCC", "C00000", true),
              shadedCell(`${counts.medium} MEDIUM`, "FFF2CC", "BF8F00", true),
              shadedCell(`${counts.low} LOW`, "E8F5E9", "2E7D32", true),
              shadedCell(`${counts.pass} PASSING`, "CCFFCC", "007000", true),
            ]}),
          ],
        }),
        new Paragraph({ children: [new TextRun({ text: "" })] }),

        new Paragraph({ children: [new TextRun({ text: "Regulatory Findings", bold: true, size: 28, color: "1C2D4F", font: "Arial" })] }),

        // Findings table
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [500, 900, 1800, 6160],
          rows: [
            new TableRow({ children: [
              shadedCell("#", "1C2D4F", "FFFFFF", true),
              shadedCell("Severity", "1C2D4F", "FFFFFF", true),
              shadedCell("Regulation", "1C2D4F", "FFFFFF", true),
              shadedCell("Finding & Recommendation", "1C2D4F", "FFFFFF", true),
            ]}),
            ...findingRows,
          ],
        }),

        new Paragraph({ children: [new TextRun({ text: "" })] }),
        new Paragraph({ children: [new TextRun({ text: "This report was generated by the Credit Card Compliance Checker Agent using Anthropic Claude. It does not constitute legal advice.", italics: true, size: 16, color: "5A5A5A", font: "Arial" })] }),
      ],
    }],
  });

  return Packer.toBuffer(doc);
}

module.exports = { generateComplianceDocx };
