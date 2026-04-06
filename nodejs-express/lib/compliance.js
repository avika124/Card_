// lib/compliance.js — Claude API calls for compliance checking
const Anthropic = require("@anthropic-ai/sdk");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const REGULATIONS = {
  udaap:       { label: "UDAAP",                description: "Unfair, Deceptive, or Abusive Acts or Practices" },
  tila:        { label: "TILA / Reg Z / CARD Act", description: "Truth in Lending Act" },
  ecoa:        { label: "ECOA / Reg B",          description: "Equal Credit Opportunity Act" },
  fcra:        { label: "FCRA / Reg V",           description: "Fair Credit Reporting Act" },
  bsa:         { label: "BSA / AML / OFAC / CIP", description: "Bank Secrecy Act / Anti-Money Laundering" },
  pci:         { label: "PCI DSS",                description: "Payment Card Industry Data Security Standard" },
  scra:        { label: "SCRA",                   description: "Servicemembers Civil Relief Act" },
  collections: { label: "Collections Conduct",    description: "FDCPA / Collection Practices" },
  sr117:       { label: "SR 11-7",                description: "Model Risk Management" },
};

const SYSTEM_PROMPT = `You are an expert credit card compliance attorney and regulatory analyst with deep expertise in consumer financial protection laws. Analyze the provided content against the specified regulations and return ONLY a valid JSON object — no markdown, no explanation, no preamble.

Return this exact structure:
{
  "overall_risk": "high|medium|low|pass",
  "summary": "2-3 sentence executive summary of findings",
  "findings": [
    {
      "regulation": "regulation name",
      "severity": "high|medium|low|pass",
      "issue": "short title of the issue or pass confirmation",
      "detail": "detailed explanation of the finding, specific concern, or why it passes",
      "excerpt": "relevant quoted text from the document that triggered this finding, or empty string if pass",
      "recommendation": "specific actionable recommendation, or empty string if pass"
    }
  ]
}

Produce one finding per regulation checked. Be specific, cite exact language when possible, and be rigorous.`;

function buildRegList(regIds) {
  return regIds
    .filter((id) => REGULATIONS[id])
    .map((id) => `- ${REGULATIONS[id].label}: ${REGULATIONS[id].description}`)
    .join("\n");
}

function parseResult(raw) {
  const clean = raw.replace(/```json|```/g, "").trim();
  return JSON.parse(clean);
}

async function checkText(text, regIds) {
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const regList = buildRegList(regIds);

  const response = await client.messages.create({
    model: process.env.MODEL || "claude-sonnet-4-20250514",
    max_tokens: parseInt(process.env.MAX_TOKENS || "4000"),
    system: SYSTEM_PROMPT,
    messages: [{
      role: "user",
      content: `Analyze the following content for compliance against these regulations:\n${regList}\n\nContent to analyze:\n---\n${text}\n---`,
    }],
  });

  const raw = response.content.map((b) => b.text || "").join("");
  return parseResult(raw);
}

async function checkImage(imageBuffer, mediaType, regIds) {
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const regList = buildRegList(regIds);
  const b64 = imageBuffer.toString("base64");

  const response = await client.messages.create({
    model: process.env.MODEL || "claude-sonnet-4-20250514",
    max_tokens: parseInt(process.env.MAX_TOKENS || "4000"),
    system: SYSTEM_PROMPT,
    messages: [{
      role: "user",
      content: [
        { type: "image", source: { type: "base64", media_type: mediaType, data: b64 } },
        { type: "text", text: `Analyze this document image for compliance against these regulations:\n${regList}\n\nExtract all text from the image and check it thoroughly.` },
      ],
    }],
  });

  const raw = response.content.map((b) => b.text || "").join("");
  return parseResult(raw);
}

async function checkFile(filePath, regIds) {
  const ext = path.extname(filePath).toLowerCase();
  const imageExts = [".jpg", ".jpeg", ".png", ".webp", ".gif"];
  const mediaMap = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif" };

  if (imageExts.includes(ext)) {
    const buf = fs.readFileSync(filePath);
    return checkImage(buf, mediaMap[ext] || "image/png", regIds);
  }

  let text = "";
  if (ext === ".txt") {
    text = fs.readFileSync(filePath, "utf-8");
  } else if (ext === ".pdf") {
    text = execSync(`pdftotext "${filePath}" -`).toString();
  } else if (ext === ".docx" || ext === ".doc") {
    text = execSync(`pandoc "${filePath}" -t plain`).toString();
  } else {
    throw new Error(`Unsupported file type: ${ext}`);
  }

  if (!text.trim()) throw new Error("Could not extract text from file.");
  return checkText(text, regIds);
}

module.exports = { checkText, checkImage, checkFile, REGULATIONS };
