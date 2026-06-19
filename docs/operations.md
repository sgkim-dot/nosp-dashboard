# NOSP 대시보드 운영 가이드

## 1. 두 BAT의 역할 (독립적)

| BAT | 무엇을 함 |
|------|------|
| `NOSP_주간업데이트.bat` | NOSP의 회차별 입찰가/낙찰가 CSV 4종 다운로드 + DB ingest. 끝나면 종료 |
| `브랜드크롤링.bat` | `brand_scrape --resume` 실행 (Naver 검색으로 광고 → brand 추출). 끝나면 자동으로 `reconcile_brands.py --apply` 호출 |

두 BAT는 서로 호출하지 않는다. 한쪽이 다른 쪽을 트리거하지 않으며 데이터 흐름도 독립적이다.

- 입찰가/낙찰가 데이터 → NOSP_주간업데이트.bat 만 처리
- 광고 집행사 데이터 → 브랜드크롤링.bat 만 처리

## 2. 환경 구조

```
[로컬 dev]                              [Production]
http://localhost:3000                   https://nosp-dashboard-sgkim-dots-projects.vercel.app
    │                                       │
    └─────────── Neon DB (공유) ────────────┘
```

- DB는 로컬 dev와 production이 **같은 Neon Postgres 인스턴스**를 본다
- BAT는 사용자 PC에서 돌며 Neon DB에 직접 쓴다
- 대시보드는 Neon DB에서 직접 읽는다 (서버사이드)

## 3. 코드 변경 → 배포 흐름

```
1. 로컬에서 코드 수정 (pnpm dev로 미리 확인)
2. 사용자가 "푸쉬해줘" 요청
3. Claude가 git commit + git push origin main
4. Vercel이 push 감지 → 자동 빌드 (1-2분)
5. production URL 자동 업데이트
```

Vercel 자동 빌드 성공/실패는 commit 후 Claude가 확인해서 알려준다.

## 4. 자주 쓰는 명령

### 로컬 dev 띄우기
```bash
cd apps/dashboard
pnpm dev
# → http://localhost:3000
```

### 다른 포트로 띄우기 (3000은 다른 프로젝트가 쓰고 있을 때) — **PM2 권장**

터미널을 닫거나 다른 작업을 해도 살아있어야 하면 PM2 로 데몬화한다.
일반 `pnpm dev:3100`은 터미널 종료/세션 끊김에 같이 죽는다.

#### 최초 1회 셋업
```bash
npm install -g pm2
cd apps/dashboard
pm2 start ecosystem.config.cjs
pm2 save     # 현재 프로세스 목록 dump.pm2 에 저장
```

#### 일상 사용
```bash
pm2 list                       # 상태 확인 (online/stopped, 재시작 횟수)
pm2 logs dashboard-3100        # 실시간 로그
pm2 restart dashboard-3100     # 코드 큰 변경 후 강제 재시작
pm2 stop dashboard-3100        # 일시 중단
pm2 delete dashboard-3100      # 완전히 내림
```

설정 파일: [apps/dashboard/ecosystem.config.cjs](../apps/dashboard/ecosystem.config.cjs)
- 포트 3100, `NEXT_DIST_DIR=.next-3100`
- `autorestart: true` — 어떤 이유로든 죽으면 자동 부활
- `max_memory_restart: 2G` — 메모리 누수 방어
- 로그: `apps/dashboard/.pm2/out.log`, `.pm2/err.log`

#### PC 재부팅 후 자동 부팅 (선택)
PM2는 Windows 자동 시작이 기본 제공 안 됨. 필요하면:
```powershell
npm install -g pm2-windows-startup
pm2-startup install
pm2 save
```
또는 매번 부팅 후 수동으로 `pm2 resurrect` 실행.

#### 그냥 한 번만 띄우려면 (PM2 없이)
```bash
cd apps/dashboard
pnpm dev:3100
# → http://localhost:3100  (distDir=.next-3100)
```
이 방식은 터미널을 닫으면 같이 죽으니, 죽지 않아야 하면 위 PM2 방식을 쓸 것.

**왜 distDir 분리하나**: Next.js 16부터 `next dev`는 `.next/dev/` 에 출력한다.
같은 폴더에서 두 dev 인스턴스를 띄우면 양쪽이 같은 디렉토리에 동시에 쓰면서
한쪽이 죽는다. `dev:3100` 과 ecosystem 둘 다 `.next-3100/` 으로 분리해서 안전.

### 브랜드 매핑 추가 후 정리
```bash
cd worker
# 1. canonical_brand.py 편집
# 2. reconcile 실행
uv run python scripts/reconcile_brands.py            # dry-run
uv run python scripts/reconcile_brands.py --apply    # 적용
# → apps/dashboard/lib/canonical-hosts.json 자동 갱신
```

자세한 브랜드 매핑 가이드: [worker/scripts/README-brands.md](../worker/scripts/README-brands.md)

### 특정 KG 강제 재스크랩
```bash
cd worker
# rkg_id를 알아낸 후 (DB 조회)
uv run python scripts/rescrape_silbi.py  # 또는 비슷한 형태로 작성
```

자세한 누락 진단: [docs/naver-ad-dot-indicator.md](naver-ad-dot-indicator.md)

## 5. 대시보드 운영 URL

| URL 종류 | 주소 |
|---------|------|
| Production (회사 공유) | `https://nosp-dashboard-sgkim-dots-projects.vercel.app` |
| GitHub repo | `https://github.com/sgkim-dot/nosp-dashboard` |
| Vercel 프로젝트 | `https://vercel.com/sgkim-dots-projects/nosp-dashboard` |
| Clerk dashboard | `https://dashboard.clerk.com` (app: NOSP Dashboard) |
| Neon DB console | `https://console.neon.tech` |

자세한 배포 설정: [docs/deployment.md](deployment.md)

## 6. 사용자 인증 (Clerk)

- **회사 도메인 화이트리스트**: `@madup.com` 이메일만 가입 허용
- 다른 도메인은 가입/사인인 자동 거부
- 사용자 관리는 https://dashboard.clerk.com 에서 직접

## 7. 일상 작업 분류

| 작업 | 빈도 | 누가 / 어떻게 |
|------|------|---------------|
| 입찰가/낙찰가 데이터 갱신 | 주 1회 | 사용자가 NOSP_주간업데이트.bat 더블클릭 |
| 광고 집행사 데이터 갱신 | 자유 | 사용자가 브랜드크롤링.bat 더블클릭 (10시간 정도 소요) |
| 새 브랜드 매핑 추가 | 발견 시 | 사용자가 URL+브랜드명 알려줌 → Claude가 HOST_TO_BRAND 편집 + reconcile + push |
| 잘못된 브랜드 정정 | 발견 시 | 같은 방식 |
| 광고 누락 (NOSP는 있다는데 우리는 0건) | 가끔 | 강제 재스크랩 요청 |
| 대시보드 UI 수정 | 자유 | 로컬 확인 → push |

## 8. 자주 발생하는 이슈

### 브랜드 정리 페이지에 같은 케이스 반복
- 원인: `HOST_TO_BRAND`에 매핑 추가했지만 reconcile 안 돌림 OR BAT가 옛 코드로 도는 중
- 해결: README-brands.md의 워크플로 참조 (매핑 → reconcile → BAT 재시작)

### 광고가 떠있는데 "집행사 없음" 표시
- 원인: Naver 광고 회전(rotation) 미스
- 해결: 강제 재스크랩 (naver-ad-dot-indicator.md 참조)

### 로컬 dev 빌드 실패 (Turbopack workspace inference)
- 원인: `next.config.ts`에 `turbopack.root` 설정 충돌
- 해결: next.config.ts를 빈 config로 유지 (Turbopack auto-detect가 보통 잘 동작)

### Vercel 빌드 실패 - "No Next.js detected"
- 원인 후보 1: package-lock.json이 불완전 (clerk init이 만든 38-dep 짧은 lockfile)
- 해결: package-lock.json 삭제 → npm install이 package.json 기반으로 fresh install

### 환경변수가 empty로 보일 때
- 원인: Vercel env add 시 `--no-sensitive` 안 줘서 값이 sensitive로 등록됨
- 해결: 재등록 시 `vercel env add ... --value <value> --no-sensitive --yes --force`

## 9. 관련 문서

- [worker/scripts/README-brands.md](../worker/scripts/README-brands.md) — 브랜드 매핑 6중 방어 + 운영
- [docs/naver-ad-dot-indicator.md](naver-ad-dot-indicator.md) — 광고 누락 진단
- [docs/deployment.md](deployment.md) — Vercel + Clerk 배포 설정 세부
