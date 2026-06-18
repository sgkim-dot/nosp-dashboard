# Vercel + Clerk 배포 세부

## 핵심 정보

| 항목 | 값 |
|------|------|
| Vercel project | `sgkim-dots-projects/nosp-dashboard` |
| Vercel project ID | `prj_0h8oNcGbTkf2GnDVdKgFFXDTra1C` |
| GitHub repo | `https://github.com/sgkim-dot/nosp-dashboard` |
| Production URL (canonical) | `https://nosp-dashboard-sgkim-dots-projects.vercel.app` |
| Clerk application | NOSP Dashboard (id `app_3FIC89YeoT5oxSWbuVHh36SINR8`) |
| Clerk frontend | `charming-macaque-26.clerk.accounts.dev` (dev instance) |

## Vercel 프로젝트 설정

- **Root Directory**: `apps/dashboard`
- **Include files outside the root directory**: **Disabled** (중요)
- **Deployment Protection**: **Disabled** (회사 전체 공유라 SSO 막으면 안 됨)
- **Framework Preset**: Next.js (자동 감지)
- **Node.js Version**: 24.x
- **Build/Install/Output Command**: 기본값 (vercel.json에서 override 안 함)

`apps/dashboard/vercel.json`:
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs"
}
```

## GitHub 연동

- Vercel ↔ GitHub: 연결됨
- Production branch: `main`
- Auto-deploy: ON
- `git push origin main` 시 자동 빌드 + 배포

## 환경변수 (Vercel Production)

7개 모두 `--no-sensitive` 플래그로 등록 (pull로 다시 가져올 수 있도록):

```
DATABASE_URL
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
NEXT_PUBLIC_CLERK_SIGN_IN_URL
NEXT_PUBLIC_CLERK_SIGN_UP_URL
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL
```

값은 `apps/dashboard/.env.local`과 동일. 환경변수 추가/변경 시 동일하게 양쪽에 반영해야 한다.

env 재push 명령 (Bash, apps/dashboard에서):
```bash
for KEY in DATABASE_URL NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY CLERK_SECRET_KEY \
           NEXT_PUBLIC_CLERK_SIGN_IN_URL NEXT_PUBLIC_CLERK_SIGN_UP_URL \
           NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL \
           NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL; do
  VAL=$(grep "^$KEY=" .env.local | head -1 | sed "s/^$KEY=//")
  vercel env rm "$KEY" production --yes >/dev/null 2>&1
  vercel env add "$KEY" production --value "$VAL" --no-sensitive --yes --force
done
```

## Clerk 설정

### 현재 상태 — Development Instance

- 화면 상단에 "Development mode" 배너 표시됨
- 사용자 100명 한도
- Rate limit: 일일 약 1000건
- Production로 전환하려면 custom domain 필요 (vercel.app 거부됨)

### Allowlist (필수 보안 설정)

Clerk dashboard → Configure → Restrictions → Allowlist:
- `madup.com` 등록됨
- 다른 도메인 가입 자동 차단

## 핵심 학습 — 배포 디버깅 (반드시 기억)

배포 셋업 중 만난 문제들과 해결책. 다음에 비슷한 일 발생 시 시간 절약.

### 1. `package-lock.json` 트랩 (가장 중요)

`clerk init`이 apps/dashboard에서 `npm install @clerk/nextjs` 실행 → **38개 deps만 잠긴 incomplete package-lock.json** 생성. 원래 pnpm workspace 기반 monorepo라 apps/dashboard에는 lockfile이 없었어야 함.

Vercel이 빌드 시 이 lockfile을 사용하면 next.js 등 핵심 deps가 빠진 채로 install → "No Next.js detected" 에러.

**해결**: `apps/dashboard/package-lock.json` 삭제. Vercel은 package.json 기반으로 fresh install하여 모든 deps 설치.

향후 dashboard에 새 npm 패키지 추가 시 주의: pnpm을 사용하든지, package-lock.json이 생기면 무조건 삭제.

### 2. Vercel CLI는 git untracked 파일을 업로드 안 함

`vercel --prod` CLI 직접 deploy 시 git-tracked 파일만 업로드 (~75 files). clerk init이 만든 untracked 파일들(proxy.ts, sign-in pages, brand-cleanup, brand-tracker 등) 누락 → 빌드 실패.

**해결**: GitHub 연동 사용. `git push` → Vercel이 GitHub repo 통째로 clone하여 빌드. 모든 파일 포함.

### 3. Monorepo Root Directory 충돌

`.vercel/` 폴더가 apps/dashboard에 있는데 Root Directory도 `apps/dashboard`로 설정하면 path 중복 (`apps/dashboard/apps/dashboard`) 에러.

**해결 (GitHub 연동 후)**: `.vercel/` 폴더가 의미 없어짐 (자동 deploy는 GitHub commit 기반). Root Directory만 Vercel UI에서 `apps/dashboard`로 설정하면 됨.

### 4. Vercel Deployment Protection이 SSO 강제

기본 설정으로 `Vercel Authentication`이 켜져 있어 모든 사용자가 Vercel 로그인 요구 → 회사 동료가 못 들어옴 → Chrome `ERR_UNSAFE_REDIRECT` 발생.

**해결**: Vercel UI → Settings → Deployment Protection → 모두 Disabled. 인증은 Clerk이 담당.

### 5. Vercel env 기본은 sensitive (pull 시 값이 빈 문자열)

`vercel env add` 기본 동작은 production env를 sensitive로 등록 → `vercel env pull`로 가져오면 값이 `""`. 로컬 빌드 시 `DATABASE_URL is not set` 등 에러.

**해결**: 등록 시 `--no-sensitive` 플래그.

### 6. Next.js 16 Turbopack workspace root inference

dev 시 `next.config.ts`에 `turbopack.root` 명시하면 오히려 깨짐. 빈 config가 자동 감지로 잘 동작.

**해결**: `next.config.ts`를 빈 default로 유지. Turbopack이 알아서 apps/dashboard를 인식.

### 7. 짧은 alias 충돌 — `nosp-dashboard.vercel.app`

Vercel의 `*.vercel.app` 글로벌 네임스페이스에서 `nosp-dashboard.vercel.app`가 다른 프로젝트와 충돌해서 응답이 이상함 (404 + Chrome ERR_UNSAFE_REDIRECT).

**해결**: 항상 긴 canonical URL 사용: `nosp-dashboard-sgkim-dots-projects.vercel.app`. 짧은 alias는 신뢰 불가.

## 백로그 (미완료)

| 작업 | 어떤 경우 필요 |
|------|----------------|
| Clerk Production instance | 회사 도메인(`dashboard.madup.com` 등) 준비 시 |
| Custom domain | Vercel custom domain 연결 + DNS 설정 + Clerk frontend URL 업데이트 |
| Production 시 "Development mode" 배너 제거 | Production instance 셋업 완료 후 자동 사라짐 |
| `*.vercel.app` 짧은 alias 충돌 해결 | Vercel support 또는 다른 alias 시도 |
