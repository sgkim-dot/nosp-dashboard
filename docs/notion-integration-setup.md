# Notion 페이지 자동 동기화 세팅

> `docs/user-guide.md` (또는 다른 markdown) 를 Notion 페이지에 자동으로 업로드하는 방법입니다.
> 1회 세팅 후, 가이드를 갱신할 때마다 한 줄 명령으로 Notion이 자동 업데이트됩니다.

---

## 0. 지금 당장 Notion에 올리는 가장 빠른 방법 (세팅 불필요)

세팅 없이도 `docs/user-guide.md` 를 Notion에 즉시 옮길 수 있습니다.

### A. VSCode / Cursor 에서 paste 하기

1. VSCode에서 `docs/user-guide.md` 열기.
2. `Ctrl + A` → `Ctrl + C` (전체 복사).
3. https://app.notion.com/p/26a5e014a2948014960dfc5488f9bea0 페이지 열기.
4. 페이지 본문 영역 클릭 → `Ctrl + V`.
5. Notion이 markdown을 자동 인식해서 **헤딩 / 표 / 리스트 / 코드블럭** 모두 변환합니다.

> **팁**: paste 시 일반 텍스트로 들어가면 `Ctrl + Shift + V` 대신 그냥 `Ctrl + V` 를 다시 시도하세요. Notion은 markdown을 "fenced source" 로 감지합니다.

### B. Notion의 "Import → Markdown" 사용

1. `docs/user-guide.md` 를 그대로 사용 (확장자 `.md` 유지).
2. Notion 페이지 좌측 상단 ⋯ 메뉴 → **Import** → **Markdown & CSV**.
3. `user-guide.md` 파일 선택.
4. Notion이 새 sub-page 로 import 합니다 (원하면 본문 위치로 drag-drop 이동).

---

## 1. 자동 동기화를 위한 1회 세팅 (선택)

자주 갱신할 예정이라면 Notion API 연동을 세팅해 두는 게 편합니다.

### Step 1 — Notion Internal Integration 토큰 발급

1. https://www.notion.so/profile/integrations 접속.
2. **+ New integration** 클릭.
3. 아래 항목 입력:
   - **Name**: `NOSP Dashboard Docs Sync` (원하는 이름)
   - **Associated workspace**: 본인 워크스페이스 선택
   - **Type**: **Internal** (기본값)
4. **Save** 클릭.
5. 다음 화면의 **Internal Integration Secret** 를 복사 (예: `ntn_xxxxxxxxxxx`).
   - 이 토큰은 **다시 볼 수 없으니** 안전한 곳에 보관 (1Password 등).

### Step 2 — 대상 페이지를 Integration 에 공유

Notion API는 권한이 명시적으로 부여된 페이지에만 접근할 수 있습니다.

1. https://app.notion.com/p/26a5e014a2948014960dfc5488f9bea0 (사용자 가이드 페이지) 열기.
2. 우측 상단 ⋯ 메뉴 → **Connections** → **Connect to** 클릭.
3. 검색칸에 `NOSP Dashboard Docs Sync` 입력 → 선택.
4. **Confirm** 클릭.

> **권한이 부모 페이지에서 상속**됩니다. 가이드 페이지의 상위(부모) 페이지에 Integration 을 붙이면 그 아래 모든 sub-page 에 자동 적용됩니다.

### Step 3 — 토큰을 환경 변수로 저장

`apps/dashboard/.env.local` 또는 본인의 셸 프로필 (`~/.bashrc`, PowerShell `$PROFILE`)에 추가:

```bash
NOTION_TOKEN=ntn_xxxxxxxxxxx
NOTION_USER_GUIDE_PAGE_ID=26a5e014a2948014960dfc5488f9bea0
```

> `.env.local` 은 git ignore 되어 있으니 안전합니다. **절대로 토큰을 commit 하지 마세요.**

PowerShell 세션에서 즉시 사용하려면:

```powershell
$env:NOTION_TOKEN = "ntn_xxxxxxxxxxx"
$env:NOTION_USER_GUIDE_PAGE_ID = "26a5e014a2948014960dfc5488f9bea0"
```

### Step 4 — 동기화 스크립트 설치

`scripts/sync-user-guide-to-notion.mjs` 를 한 번만 작성합니다 (이미 만들어져 있으면 skip).

```bash
# 패키지 한 번만 설치
cd C:\Users\MADUP\Documents\SearchingviewNewProduct
pnpm add -D @notionhq/client
```

스크립트 예시 (이미 본 레포의 `scripts/sync-user-guide-to-notion.mjs` 에 들어 있음):

```js
import { Client } from "@notionhq/client";
import fs from "node:fs";

const NOTION_TOKEN = process.env.NOTION_TOKEN;
const PAGE_ID = process.env.NOTION_USER_GUIDE_PAGE_ID;
if (!NOTION_TOKEN || !PAGE_ID) {
  console.error("NOTION_TOKEN / NOTION_USER_GUIDE_PAGE_ID env vars required");
  process.exit(1);
}
const notion = new Client({ auth: NOTION_TOKEN });
const md = fs.readFileSync("docs/user-guide.md", "utf8");

// 본문을 단순한 paragraph/heading 블록으로 변환 (최소 구현)
const blocks = md.split(/\n/).map((line) => {
  if (line.startsWith("# ")) {
    return { object: "block", type: "heading_1",
      heading_1: { rich_text: [{ type: "text", text: { content: line.slice(2) } }] } };
  }
  if (line.startsWith("## ")) {
    return { object: "block", type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: line.slice(3) } }] } };
  }
  if (line.startsWith("### ")) {
    return { object: "block", type: "heading_3",
      heading_3: { rich_text: [{ type: "text", text: { content: line.slice(4) } }] } };
  }
  return { object: "block", type: "paragraph",
    paragraph: { rich_text: [{ type: "text", text: { content: line } }] } };
});

// 기존 자식 블록 삭제 후 새로 추가
const existing = await notion.blocks.children.list({ block_id: PAGE_ID, page_size: 100 });
for (const b of existing.results) {
  await notion.blocks.delete({ block_id: b.id });
}
// Notion API 는 한 번에 100 블록까지만 받음 → 청크로 쪼개기
for (let i = 0; i < blocks.length; i += 100) {
  await notion.blocks.children.append({
    block_id: PAGE_ID,
    children: blocks.slice(i, i + 100),
  });
}
console.log(`✓ Synced ${blocks.length} blocks to Notion page ${PAGE_ID}`);
```

> **주의**: 위 스크립트는 **최소 구현**입니다. 표·코드블럭·인라인 강조 같은 markdown 요소는 변환되지 않습니다. 표·코드 보존이 필요하면 `martian` (`pnpm add -D @tryfabric/martian`) 같은 라이브러리로 markdown → Notion blocks 변환을 쓰세요. 그 경우 위 스크립트의 변환 로직만 교체하면 됩니다.

### Step 5 — 갱신 시 명령 한 줄

```bash
node scripts/sync-user-guide-to-notion.mjs
```

성공 시 출력:

```
✓ Synced 482 blocks to Notion page 26a5e014a2948014960dfc5488f9bea0
```

---

## 2. 추천 워크플로

가이드 갱신 패턴:

1. `docs/user-guide.md` 편집.
2. PR 리뷰 / 머지.
3. `node scripts/sync-user-guide-to-notion.mjs` 실행 → Notion 동기화.
4. (선택) git hook 으로 main 머지 시 자동 실행.

자동화까지 가려면 GitHub Actions 워크플로를 추가하면 됩니다 — 필요하다면 별도 요청 주세요.

---

## 3. 트러블슈팅

| 에러 | 원인 | 해결 |
|------|------|------|
| `Could not find page with ID` | Integration 이 페이지에 공유 안 됨 | Step 2 다시 확인 |
| `Unauthorized` | 토큰 오타 또는 만료 | Integration 페이지에서 새 토큰 재발급 |
| `validation_error: should be defined` | Page ID 형식 오류 | URL의 마지막 32자 hex (하이픈 없이) |
| `Conflict: Block already exists` | 동시 실행 충돌 | 한 번에 한 명만 실행 |

---

## 4. 보안 체크리스트

- [ ] `.env.local` 이 `.gitignore` 에 포함되어 있는가? (이미 포함되어 있음)
- [ ] 토큰을 슬랙·이메일에 평문 공유하지 않았는가?
- [ ] Integration 이 **필요한 페이지에만** 공유되어 있는가? (전체 워크스페이스 X)
- [ ] 토큰 유출 의심 시 즉시 https://www.notion.so/profile/integrations 에서 재발급
