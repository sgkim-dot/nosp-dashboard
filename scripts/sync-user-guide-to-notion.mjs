#!/usr/bin/env node
/**
 * docs/user-guide.md  →  Notion 페이지 자동 동기화
 *
 * 사용법:
 *   1) .env.local 에 NOTION_TOKEN, NOTION_USER_GUIDE_PAGE_ID 설정
 *   2) pnpm docs:sync
 *
 * 동작:
 *   - 대상 Notion 페이지의 기존 자식 블록을 모두 삭제
 *   - docs/user-guide.md 를 markdown → Notion blocks 로 변환 (martian)
 *   - 새 블록을 페이지에 append (100개씩 청크)
 *   - 페이지 제목을 "NOSP 대시보드 사용 가이드 (YYYY-MM-DD 갱신)" 으로 업데이트
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@notionhq/client";
import { markdownToBlocks } from "@tryfabric/martian";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

// 1. .env.local 로드 (있으면)
const envPath = path.join(ROOT, ".env.local");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = val;
  }
}

const NOTION_TOKEN = process.env.NOTION_TOKEN;
const PAGE_ID = process.env.NOTION_USER_GUIDE_PAGE_ID;
const GUIDE_PATH = path.join(ROOT, "docs", "user-guide.md");

if (!NOTION_TOKEN) {
  console.error("❌ NOTION_TOKEN 환경변수가 없습니다.");
  console.error("   .env.local 에 다음을 추가하세요:");
  console.error("   NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
  process.exit(1);
}
if (!PAGE_ID) {
  console.error("❌ NOTION_USER_GUIDE_PAGE_ID 환경변수가 없습니다.");
  console.error("   .env.local 에 다음을 추가하세요:");
  console.error("   NOTION_USER_GUIDE_PAGE_ID=26a5e014a2948014960dfc5488f9bea0");
  process.exit(1);
}
if (!fs.existsSync(GUIDE_PATH)) {
  console.error(`❌ 가이드 파일을 찾을 수 없습니다: ${GUIDE_PATH}`);
  process.exit(1);
}

const notion = new Client({ auth: NOTION_TOKEN });

async function main() {
  console.log(`▶ 가이드 파일 읽기: docs/user-guide.md`);
  const md = fs.readFileSync(GUIDE_PATH, "utf8");

  console.log(`▶ markdown → Notion blocks 변환 (martian)`);
  const blocks = markdownToBlocks(md);
  console.log(`  변환된 블록 수: ${blocks.length}`);

  console.log(`▶ Notion API 호환 sanitize (상대/anchor 링크 → plain text)`);
  let strippedLinks = 0;
  function sanitizeRichText(arr) {
    if (!Array.isArray(arr)) return;
    for (const rt of arr) {
      if (rt?.text?.link) {
        const url = rt.text.link.url;
        const isHttp = typeof url === "string" && /^https?:\/\//i.test(url);
        const isMailto = typeof url === "string" && /^mailto:/i.test(url);
        if (!isHttp && !isMailto) {
          rt.text.link = null;
          strippedLinks += 1;
        }
      }
    }
  }
  function walk(node) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      for (const child of node) walk(child);
      return;
    }
    for (const [key, val] of Object.entries(node)) {
      if (key === "rich_text" && Array.isArray(val)) {
        sanitizeRichText(val);
      } else if (val && typeof val === "object") {
        walk(val);
      }
    }
  }
  walk(blocks);
  console.log(`  ${strippedLinks}개 링크를 plain text로 변환`);

  console.log(`▶ 기존 자식 블록 삭제`);
  let cursor;
  let deletedCount = 0;
  do {
    const res = await notion.blocks.children.list({
      block_id: PAGE_ID,
      page_size: 100,
      start_cursor: cursor,
    });
    for (const b of res.results) {
      try {
        await notion.blocks.delete({ block_id: b.id });
        deletedCount += 1;
      } catch (e) {
        console.warn(`  ⚠ 블록 ${b.id} 삭제 실패 (무시): ${e.message}`);
      }
    }
    cursor = res.has_more ? res.next_cursor : undefined;
  } while (cursor);
  console.log(`  삭제 완료: ${deletedCount}개`);

  console.log(`▶ 새 블록 append (100개씩 청크)`);
  for (let i = 0; i < blocks.length; i += 100) {
    const chunk = blocks.slice(i, i + 100);
    await notion.blocks.children.append({
      block_id: PAGE_ID,
      children: chunk,
    });
    console.log(`  ${Math.min(i + 100, blocks.length)}/${blocks.length} append 완료`);
  }

  console.log(`▶ 페이지 제목 업데이트`);
  const today = new Date().toISOString().slice(0, 10);
  const newTitle = `NOSP 대시보드 사용 가이드 (${today} 갱신)`;
  try {
    await notion.pages.update({
      page_id: PAGE_ID,
      properties: {
        title: {
          title: [{ type: "text", text: { content: newTitle } }],
        },
      },
    });
    console.log(`  제목: "${newTitle}"`);
  } catch (e) {
    console.warn(`  ⚠ 제목 업데이트 실패 (무시 가능, 권한 부족일 수 있음): ${e.message}`);
  }

  console.log(`\n✅ 동기화 완료 — 페이지 ID ${PAGE_ID}`);
  console.log(`   https://www.notion.so/${PAGE_ID.replace(/-/g, "")}`);
}

main().catch((err) => {
  console.error("\n❌ 동기화 실패:");
  console.error(err?.body ?? err);
  process.exit(1);
});
