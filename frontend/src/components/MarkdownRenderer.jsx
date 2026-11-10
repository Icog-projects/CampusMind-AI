import React from 'react';

/**
 * Clean Markdown Renderer for CampusMind AI.
 * Handles headings, bold, italic, inline code, code blocks, bullet points,
 * numbered lists, paragraphs, and cleans citation markers like 【1】 or ?1?.
 */
export const MarkdownRenderer = ({ content }) => {
  if (!content) return null;

  // 1. Clean weird encoding or artifact markers, e.g. 【1】 or ?1? or [1] into clean citation badges
  let cleanText = content
    // Replace Chinese/Unicode brackets 【1】 or corrupted ?1? with [1]
    .replace(/[【\[]\s*(\d+)\s*[】\]]/g, '[$1]')
    .replace(/\?(\d+)\?/g, '[$1]')
    // Remove consecutive redundant blank lines
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // 2. Split text into lines for structured block rendering
  const lines = cleanText.split('\n');
  const elements = [];
  let currentList = null;
  let inCodeBlock = false;
  let codeBuffer = [];

  const flushList = () => {
    if (currentList) {
      if (currentList.type === 'ul') {
        elements.push(
          <ul key={`list-${elements.length}`} className="my-2 space-y-1 pl-5 list-disc list-outside text-slate-700">
            {currentList.items.map((item, i) => (
              <li key={i} className="leading-relaxed">{renderInline(item)}</li>
            ))}
          </ul>
        );
      } else {
        elements.push(
          <ol key={`list-${elements.length}`} className="my-2 space-y-1 pl-5 list-decimal list-outside text-slate-700">
            {currentList.items.map((item, i) => (
              <li key={i} className="leading-relaxed">{renderInline(item)}</li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Check code blocks
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        // Closing code block
        elements.push(
          <pre key={`code-${index}`} className="my-2.5 p-3 rounded-lg bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto">
            <code>{codeBuffer.join('\n')}</code>
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        flushList();
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      return;
    }

    // Blank lines
    if (!trimmed) {
      flushList();
      return;
    }

    // Heading 3: ###
    if (trimmed.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={`h3-${index}`} className="text-sm font-bold text-slate-900 mt-3 mb-1">
          {renderInline(trimmed.substring(4))}
        </h4>
      );
      return;
    }

    // Heading 2: ##
    if (trimmed.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={`h2-${index}`} className="text-base font-bold text-slate-900 mt-3.5 mb-1.5">
          {renderInline(trimmed.substring(3))}
        </h3>
      );
      return;
    }

    // Heading 1: #
    if (trimmed.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={`h1-${index}`} className="text-lg font-extrabold text-slate-900 mt-4 mb-2">
          {renderInline(trimmed.substring(2))}
        </h2>
      );
      return;
    }

    // Unordered List item: - or *
    if (/^[-*]\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^[-*]\s+/, '');
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [itemText] };
      } else {
        currentList.items.push(itemText);
      }
      return;
    }

    // Ordered List item: 1.
    if (/^\d+\.\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^\d+\.\s+/, '');
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [itemText] };
      } else {
        currentList.items.push(itemText);
      }
      return;
    }

    // Normal paragraph
    flushList();
    elements.push(
      <p key={`p-${index}`} className="my-1.5 leading-relaxed text-slate-800">
        {renderInline(trimmed)}
      </p>
    );
  });

  flushList();

  return <div className="markdown-body space-y-1">{elements}</div>;
};

/**
 * Renders inline styling (bold, italic, code, citation badges [1])
 */
function renderInline(text) {
  if (!text) return text;

  // Tokenize regex for inline elements
  // Matches: `code`, **bold**, *italic*, and [1] citations
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\])/g;
  const parts = text.split(regex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Inline code `...`
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return (
        <code key={i} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-[11px] border border-slate-200">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Bold **...**
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
    }

    // Italic *...*
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i} className="italic text-slate-700">{part.slice(1, -1)}</em>;
    }

    // Citation badge [1]
    const citeMatch = part.match(/^\[(\d+)\]$/);
    if (citeMatch) {
      return (
        <span
          key={i}
          className="inline-flex items-center justify-center mx-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700 border border-blue-200 align-baseline cursor-default select-none"
          title={`Citation Reference [${citeMatch[1]}]`}
        >
          {citeMatch[1]}
        </span>
      );
    }

    return part;
  });
}

