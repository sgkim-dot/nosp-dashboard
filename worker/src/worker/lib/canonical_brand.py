"""Map advertiser hostnames → canonical Korean brand names.

For most advertisers the hostname is the unique identifier
(`direct.samsungfire.com` → 삼성화재).

For Naver-hosted platforms (`brand.naver.com`, `smartstore.naver.com`),
many different advertisers share the same hostname, so we extend the
identifier with the first path segment (`brand.naver.com/lactiv`,
`smartstore.naver.com/yepp`). Both forms work as keys in HOST_TO_BRAND.

When a new advertiser is encountered, add an entry below. For unknown
hosts the `guess_from_display` heuristic returns the first word of the
ad copy as a best-guess brand.
"""

from __future__ import annotations

import re

# Naver platforms whose path segment matters for brand identity.
PLATFORM_HOSTS = {
    "brand.naver.com",
    "smartstore.naver.com",
    "shopping.naver.com",
    "blog.naver.com",
}


# Naver 쇼핑라이브 hosts. Unlike PLATFORM_HOSTS (where the FIRST path segment
# is the advertiser slug, e.g. /lactiv), 쇼핑라이브 routes look like
# /lives/{liveId} or /livebridge/{liveId} — the literal first segment
# ("lives", "livebridge") is just the route name, and the *second* segment
# (the live ID) is what identifies the advertiser's stream. We therefore
# keep BOTH segments as the identifier:
#     view.shoppinglive.naver.com/lives/1920628
# Without this, every shopping-live ad would collapse to the same host
# "view.shoppinglive.naver.com" with no distinguishing info.
SHOPPING_LIVE_HOSTS = {
    "shoppinglive.naver.com",
    "view.shoppinglive.naver.com",
    "m.shoppinglive.naver.com",
}


# Generic redirect targets that are NEVER an advertiser identity. When an
# ad's landing URL ends up at one of these hosts (e.g. the advertiser
# linked a YouTube product video instead of their own site), the host is
# meaningless for brand attribution. Treat as "unresolved" so the brand
# falls back to display-side matching (DISPLAY_CANONICAL / DISPLAY_FULL_
# CANONICAL / guess_from_display).
GENERIC_REDIRECT_HOSTS: set[str] = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.me",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    # blog.naver.com is handled separately by platform_business_name()
    # — do NOT include it here, that would break legit blog-based mappings
}


def normalize_host(host: str | None) -> str | None:
    """Canonicalize host so equivalent advertiser URLs share one identifier.

    - Strip leading 'm.' (mobile subdomain)
    - Strip leading 'www.' (the only common ASCII variant prefix; advertisers
      that serve both `www.brand.com` and `brand.com` would otherwise create
      two separate brand rows).
    """
    if not host:
        return None
    host = host.lower().strip()
    if host.startswith("m."):
        host = host[2:]
    if host.startswith("www."):
        host = host[4:]
    return host


def platform_business_name(
    host: str | None, path: str | None, query: str | None = None
) -> str | None:
    """For platform hosts, return `host/{advertiser-id}` as canonical ID.

    Special handling for Naver Blog:
      Naver Blog has two URL shapes:
        (a) clean path  → `blog.naver.com/{blogId}/{postNo?}`
        (b) navigation  → `blog.naver.com/PostView.naver?blogId={blogId}&logNo=...`
                          `blog.naver.com/NBlogTop.naver?blogId=...`
                          `blog.naver.com/PostList.naver?blogId=...`
      For (b) the first path segment is `PostView.naver` etc — NOT the blog
      identity. We must read `blogId` from the query string instead.
    """
    h = normalize_host(host)

    # 쇼핑라이브: keep `{route}/{liveId}` as the identifier (route is "lives"
    # or "livebridge" — both treated as part of the slug since the liveId
    # alone is what matters but we preserve the route prefix for clarity).
    if h in SHOPPING_LIVE_HOSTS:
        segs = [s for s in (path or "").strip("/").split("/") if s]
        if len(segs) >= 2:
            return f"{h}/{segs[0]}/{segs[1]}"
        return h

    if h not in PLATFORM_HOSTS:
        return None
    seg = (path or "").strip("/").split("/")[0] if (path or "").strip("/") else ""

    # Naver Blog navigation pages: extract `blogId` from query string.
    # NBlogTop.naver also exposes a `Qs` param (re-encoded original target,
    # e.g. `/samsungfund/224277684412`) — when present that's the truer
    # advertiser identity, since `blogId` may point to a Naver-internal
    # routing blog rather than the advertiser's own.
    if h == "blog.naver.com" and seg.endswith(".naver"):
        if query:
            from urllib.parse import parse_qs

            qs = parse_qs(query)
            # Prefer the original `Qs` target if it carries a path-shape blogId
            qs_target = (qs.get("Qs") or qs.get("qs") or [""])[0].strip()
            if qs_target:
                # Qs is like "/samsungfund/12345" — take first segment
                qs_seg = qs_target.strip("/").split("/")[0]
                if qs_seg and not qs_seg.endswith(".naver"):
                    return f"{h}/{qs_seg}"
            blog_id = (qs.get("blogId") or qs.get("blogid") or [""])[0].strip()
            if blog_id:
                return f"{h}/{blog_id}"
        # Couldn't extract anything useful → return host only so it doesn't
        # get mis-keyed as `blog.naver.com/PostView.naver`.
        return h

    return f"{h}/{seg}" if seg else h

# Hostname → canonical Korean brand name.
# Hostnames are the result of httpx redirect resolution (`.url.host`).
HOST_TO_BRAND: dict[str, str] = {
    # ─── 손해보험 ─────────────────────────────
    "direct.samsungfire.com": "삼성화재",
    "www.samsungfire.com": "삼성화재",
    "direct.hi.co.kr": "현대해상",
    "mdirect.hi.co.kr": "현대해상",
    "www.hi.co.kr": "현대해상",
    "hi.co.kr": "현대해상",
    "direct.kbinsure.co.kr": "KB손해보험",
    "mdirect.kbinsure.co.kr": "KB손해보험",
    "www.kbinsure.co.kr": "KB손해보험",
    "store.meritzfire.com": "메리츠화재",
    "direct.meritzfire.com": "메리츠화재",
    "www.meritzfire.com": "메리츠화재",
    "www.carrotins.com": "캐롯손해보험",
    "m.direct-db.co.kr": "DB손해보험",
    "www.directdb.co.kr": "DB손해보험",
    "www.directidb.co.kr": "DB손해보험",
    "mdirect.dbinsure.co.kr": "DB손해보험",
    "www.dbinsure.co.kr": "DB손해보험",
    "dbinsure.co.kr": "DB손해보험",
    "db-direct.co.kr": "DB손해보험",
    "direct-db.co.kr": "DB손해보험",
    "directdb-corp.kr": "DB손해보험",
    "directdb-oneday.kr": "DB손해보험",
    "www.directdb-oneday.kr": "DB손해보험",
    "m.directdb-oneday.kr": "DB손해보험",
    # ─── 추가 매핑 (2026-06-16 batch) ───────────
    "flimeal.com": "플라이밀",
    "www.flimeal.com": "플라이밀",
    "m.flimeal.com": "플라이밀",
    "beaverstorelab.com": "비버 매장연구소",
    "www.beaverstorelab.com": "비버 매장연구소",
    "m.beaverstorelab.com": "비버 매장연구소",
    "lefee.co.kr": "르페",
    "www.lefee.co.kr": "르페",
    "m.lefee.co.kr": "르페",
    "design-book.co.kr": "디자인교과서",
    "www.design-book.co.kr": "디자인교과서",
    "m.design-book.co.kr": "디자인교과서",
    "nordicsleep.co.kr": "노르딕슬립",
    "www.nordicsleep.co.kr": "노르딕슬립",
    "m.nordicsleep.co.kr": "노르딕슬립",
    "thinki.org": "띵크아이",
    "www.thinki.org": "띵크아이",
    "m.thinki.org": "띵크아이",
    "directidb.co.kr": "DB손해보험",
    "meritzevent.com": "메리츠화재",
    "zowie.benq.com": "BenQ Zowie",
    "www.4fact.co.kr": "포팩트",
    "4fact.co.kr": "포팩트",
    "thome.kr": "Thome",
    "www.oliveyoung.co.kr": "올리브영",
    "oliveyoung.co.kr": "올리브영",
    "m.oliveyoung.co.kr": "올리브영",
    "www.purinapetcare.co.kr": "퓨리나",
    "purinapetcare.co.kr": "퓨리나",
    "direct.lghellovision.net": "헬로모바일",
    "lghellovision.net": "헬로모바일",
    "www.lghellovision.net": "헬로모바일",
    # ─── 추가 매핑 (2026-05-29) ───────────────
    "gamtanstore.com": "감탄",
    "www.gamtanstore.com": "감탄",
    "mongze.kr": "몽제",
    "www.mongze.kr": "몽제",
    "klug.kr": "클럭",
    "www.klug.kr": "클럭",
    "nstationmall.com": "내셔널지오그래픽",
    "www.nstationmall.com": "내셔널지오그래픽",
    "store.sony.co.kr": "소니",
    "hulec.co.kr": "휴렉",
    "www.hulec.co.kr": "휴렉",
    "quezone.co.kr": "쾌존",
    "www.quezone.co.kr": "쾌존",
    "kr.canon": "캐논",
    "www.dealpang.com": "딜팡",
    "dealpang.com": "딜팡",
    "m.dealpang.com": "딜팡",
    "blog.naver.com/samsungfund": "삼성자산운용",
    "blog.naver.com/bgfe215": "쾌존",
    "blog.naver.com/ocoohs": "오쿠",
    "(주)센스맘": "센스맘",
    "brand.naver.com/sensemom": "센스맘",
    "hello.matetech.co.kr": "메이트",
    "matetech.co.kr": "메이트",
    "www.matetech.co.kr": "메이트",
    "www.newvein.co.kr": "대원제약",
    "newvein.co.kr": "대원제약",
    "www.torder.com": "티오더",
    "torder.com": "티오더",
    "www.heydealer.com": "헤이딜러",
    "heydealer.com": "헤이딜러",
    "m.heydealer.com": "헤이딜러",
    "www.wonderbramall.co.kr": "원더브라",
    "wonderbramall.co.kr": "원더브라",
    "andar.co.kr": "안다르",
    "www.andar.co.kr": "안다르",
    "m.andar.co.kr": "안다르",
    "www.wart.or.kr": "위아트",
    "wart.or.kr": "위아트",
    "www.wart.co.kr": "위아트",
    "wart.co.kr": "위아트",
    "m.hej.life": "헤이홈",
    "hej.life": "헤이홈",
    "www.hej.life": "헤이홈",
    "carmim.co.kr": "카밈",
    "www.carmim.co.kr": "카밈",
    "hyperbrain.co.kr": "브레인미",
    "www.hyperbrain.co.kr": "브레인미",
    # ─── 호스트 깨짐 정정 (2026-06-01) ─────────
    "www.esthermall.co.kr": "에스더포뮬러",
    "esthermall.co.kr": "에스더포뮬러",
    "www.coway.com": "코웨이",
    "coway.com": "코웨이",
    "curtainmaster.co.kr": "커튼명장",
    "www.curtainmaster.co.kr": "커튼명장",
    "modelomall.co.kr": "모델로",
    "www.modelomall.co.kr": "모델로",
    "keyang.kr": "계양공구",
    "www.keyang.kr": "계양공구",
    "home.orderqueen.kr": "오더퀸",
    "orderqueen.kr": "오더퀸",
    "kr.roborock.com": "로보락",
    "mebetter.co.kr": "미베러",
    "www.mebetter.co.kr": "미베러",
    "iubis.net": "유비스가구",
    "www.iubis.net": "유비스가구",
    "shop.ivenet.co.kr": "아이배냇",
    "www.shop.ivenet.co.kr": "아이배냇",
    "ivenet.co.kr": "아이배냇",
    "vancleefarpels.com": "반클리프아펠",
    "www.vancleefarpels.com": "반클리프아펠",
    "m.farfe.co.kr": "파르페by알레르망",
    "farfe.co.kr": "파르페by알레르망",
    "www.farfe.co.kr": "파르페by알레르망",
    "overthe.co.kr": "오버더",
    "www.overthe.co.kr": "오버더",
    "decosleep.com": "데코슬립",
    "www.decosleep.com": "데코슬립",
    "www.edumbc.net": "MBC아카데미",
    "edumbc.net": "MBC아카데미",
    "1544-0024.co.kr": "로젠이사",
    "www.1544-0024.co.kr": "로젠이사",
    "smartstore.naver.com/evckorea": "이브이씨코리아",
    "gfound.org": "지파운데이션",
    "www.gfound.org": "지파운데이션",
    "apply.iscu.ac.kr": "서울사이버대학교",
    "iscu.ac.kr": "서울사이버대학교",
    "www.iscu.ac.kr": "서울사이버대학교",
    "go.kycu.ac.kr": "건양사이버대학교",
    "kycu.ac.kr": "건양사이버대학교",
    "www.kycu.ac.kr": "건양사이버대학교",
    "beolmoon.com": "벌문",
    "www.beolmoon.com": "벌문",
    # 올리브영 단축 URL (oy.run) — 모든 oliveyoung 변형은 올리브영으로 통일
    "oy.run": "올리브영",
    "www.oy.run": "올리브영",
    "m.oliveyoung.co.kr": "올리브영",
    "theleadersnote.com": "더리더스노트",
    "www.theleadersnote.com": "더리더스노트",
    "lguplus.com": "LG유플러스",
    "www.lguplus.com": "LG유플러스",
    "m.lguplus.com": "LG유플러스",
    # 깨진 호스트 재정정 (2026-06-02) ─ regex 경로 제거 + URL host 강제
    "hej.life": "헤이홈",
    "www.hej.life": "헤이홈",
    "brand.naver.com/4fact": "포팩트",
    "curtainmaster.kr": "커튼명장",
    "www.curtainmaster.kr": "커튼명장",
    "agabang2025.cafe24.com": "아가방",
    "계양공구": "계양공구",
    "(주)알레르망": "파르페by알레르망",
    "alice.lotteins.co.kr": "롯데손해보험",
    "www.lotteins.co.kr": "롯데손해보험",
    "day.hanainsure.co.kr": "하나손해보험",
    "www.hanainsure.co.kr": "하나손해보험",
    "hanainsure.co.kr": "하나손해보험",
    "www.heungkukfire.co.kr": "흥국화재",
    "direct.heungkukfire.co.kr": "흥국화재",
    "www.nhfire.co.kr": "농협손해보험",
    "www.dongbuins.com": "DB손해보험",
    # ─── 추가 매핑 (2026-06-02 batch) ───────────
    "bodranmall.com": "발렌",
    "www.bodranmall.com": "발렌",
    "evckorea.cafe24.com": "이브이씨코리아",
    "webiommall.co.kr": "위바이옴",
    "www.webiommall.co.kr": "위바이옴",
    # ─── 생명보험 ─────────────────────────────
    "direct.samsunglife.com": "삼성생명",
    "www.samsunglife.com": "삼성생명",
    "mdirect.e-lina.co.kr": "라이나생명",
    "mdirect.lina.co.kr": "라이나생명",
    "direct.lina.co.kr": "라이나생명",
    "www.lina.co.kr": "라이나생명",
    "lina.co.kr": "라이나생명",
    # ─── 학습 / 교육 ──────────────────────────
    "milkt.co.kr": "밀크T",
    "www.milkt.co.kr": "밀크T",
    "grade-laboratory.com": "착한학점연구소",
    "www.grade-laboratory.com": "착한학점연구소",
    "sales.hr.aia.co.kr": "AIA생명",
    "www.aia.co.kr": "AIA생명",
    "hwgi.kr": "한화손해보험",
    "www.hwgi.kr": "한화손해보험",
    "m.hwgi.kr": "한화손해보험",
    "www.hanwhalife.com": "한화생명",
    "www.kyobo.co.kr": "교보생명",
    "direct.kyobo.co.kr": "교보생명",
    "www.tongyangcareer.com": "동양생명",
    "www.fubonhyundailife.com": "푸본현대생명",
    "www.shinhanlife.com": "신한라이프",
    "www.miraeassetlife.com": "미래에셋생명",
    # ─── 의약/건강 ────────────────────────────
    "www.rogaine.co.kr": "로게인",
    "rogaine.co.kr": "로게인",
    # ─── 가전 ────────────────────────────────
    "www.coway.com": "코웨이",
    "www.cuckoo.co.kr": "쿠쿠",
    "cuckoo.co.kr": "쿠쿠",
    "m.cuckoo.co.kr": "쿠쿠",
    "www.skmagic.com": "SK매직",
    "www.dyson.co.kr": "다이슨",
    "dyson.co.kr": "다이슨",
    "www.ppz.kr": "퍼피즈",
    "ppz.kr": "퍼피즈",
    # ─── 통신/방송 ────────────────────────────
    "www.skylife.co.kr": "스카이라이프",
    "skylife.co.kr": "스카이라이프",
    "www.ktmmobile.com": "KT M모바일",
    "ktmmobile.com": "KT M모바일",
    "m.ktmmobile.com": "KT M모바일",
    # ─── 기타 ────────────────────────────────
    "www.bullsonemall.com": "불스원",
    "1588-1191.com": "119퀵화물",
    "www.piaget.com": "피아제",
    "eltcosmetic.com": "이엘티코스메틱",
    "blanc101.com": "블랑101",
    # ─── Legacy Korean business_name keys (from old landing-page extraction) ──
    "에스더포뮬러(주": "에스더포뮬러",
    "커튼명장": "커튼명장",
    "로젠이사주식회사": "로젠이사",
    "베이비포": "베이비포",
    "유비스가구": "유비스가구",
    "릴렉스젠": "릴렉스젠",
    "주식회사 컨테이저스": "컨테이저스",
    "주식회사 이브이씨코리아": "이브이씨코리아",
    "__unverified__::굿앤굿 어린이종합보험Q": "현대해상",
    "__unverified__::현대해상 굿앤굿어린이종합보험Q": "현대해상",
    # ─── User-mapped 2026-06-29 batch (개별 정정) ─────────────
    "conects.com": "공단기",
    "www.conects.com": "공단기",
    "gong.conects.com": "공단기",
    "dpharm.co.kr": "동아제약",
    "www.dpharm.co.kr": "동아제약",
    "m.dpharm.co.kr": "동아제약",
    "staymore.co.kr": "스테이모어",
    "www.staymore.co.kr": "스테이모어",
    "m.staymore.co.kr": "스테이모어",
    # ─── User-confirmed 2026-06-30 batch (cleanup 제외용 — 정상 브랜드) ──
    # 휴리스틱이 "짧은 이름"으로 잘못 flag하는 정상 브랜드들. HOST_TO_BRAND에
    # 명시 등록되면 getSuspectBrands가 자동 skip (CANONICAL_HOSTS.has 조건).
    "shokz.co.kr": "샥즈",
    "www.shokz.co.kr": "샥즈",
    "piev.kr": "피에브",
    "www.piev.kr": "피에브",
    "baro-lab.com": "바로랩",
    "www.baro-lab.com": "바로랩",
    "lazybee.co.kr": "레이지비",
    "www.lazybee.co.kr": "레이지비",
    "makeshop.co.kr": "메이크샵",
    "www.makeshop.co.kr": "메이크샵",
    # ─── User-mapped 2026-06-26 batch (xlsx 일괄 적용) ─────────────
    "direct.hanwhalife.com": "한화생명",
    "brand.naver.com/delico_korea": "딜리코",
    "brand.naver.com/hoydeco": "호이데코",
    "smartstore.naver.com/yourgreens": "유여그린",
    "brand.naver.com/innisfree": "이니스프리",
    "smartstore.naver.com/indus_shop": "인더스",
    "smartstore.naver.com/otod": "오토드",
    "go.sdu.ac.kr": "서울디지털대학교",
    "chungho.com": "청호나이스",
    "vipla.co.kr": "바이플라",
    "smartstore.naver.com/ygcommerce": "YG커머스",
    "bodyfriend.co.kr": "바디프랜드",
    "brand.naver.com/chansol": "헨켈홈케어",
    "brand.naver.com/philipsmassage": "필립스마사지",
    "brand.naver.com/ocoo": "오쿠",
    "smartstore.naver.com/frebits": "프레비츠",
    "brand.naver.com/timetorun": "타임투런",
    "smartstore.naver.com/sidam_": "시담(마비스&프로라소)",
    "smartstore.naver.com/purezen_": "퓨어젠",
    "brand.naver.com/royalseries": "로얄시리즈",
    "brand.naver.com/dirtylinen": "더티린넨",
    "brand.naver.com/tophealth": "탑헬스",
    "brand.naver.com/nubore": "누보레",
    "brand.naver.com/happyrun": "해피런",
    "smartstore.naver.com/mediinlab": "메디안랩",
    "smartstore.naver.com/ginsenga": "진생가",
    "brand.naver.com/idealrecipe": "아이디얼레시피",
    "brand.naver.com/sooneehome": "수니홈",
    "brand.naver.com/proteeone": "프로티원",
    "amoremall.com": "슈퍼바이오틱스",
    "brand.naver.com/ckdhc": "종근당건강",
    "blog.naver.com/etf_kodex": "삼성자산운용",
    "smartstore.naver.com/krdreame": "드리미",
    "brand.naver.com/nestlestore": "네슬레",
    "smartstore.naver.com/oribam": "오리밤",
    "orionstar.kr": "오리온스타",
    "smartstore.naver.com/tronixone": "몽제",
    "smartstore.naver.com/tube_shop": "튜브샵",
    "brand.naver.com/roborock": "로보락",
    "brand.naver.com/yuhan": "유한양행",
    "lifeplanet.co.kr": "교보라플",
    "smartstore.naver.com/klarr": "클라",
    "brand.naver.com/lgpral": "LG프라엘",
    "brand.naver.com/polident": "폴리덴트",
    "brand.naver.com/kidsten": "키즈텐",
    "directdb.co.kr": "DB손해보험",
    "smartstore.naver.com/lifelongsecret": "평생비책",
    "springair.kr": "스프링에어",
    "smartstore.naver.com/pienarin": "피어나린",
    "smartstore.naver.com/bdplab": "비디피랩",
    "brand.naver.com/cybex": "싸이벡스",
    "brand.naver.com/gaea_official": "가이아",
    "smartstore.naver.com/donomall": "도노몰",
    "brand.naver.com/muhwadang": "무화당",
    "meditherapy.co.kr": "메디테라피",
    "smartstore.naver.com/ccambbak": "깜빡",
    "smartstore.naver.com/zappyrex": "재피렉스",
    "smartstore.naver.com/elephbaby": "엘리프",
    "smartstore.naver.com/nutritiontree": "뉴트리션트리",
    "dwhcmall.com": "대웅제약",
    "go.khcu.ac.kr": "경희사이버대학교",
    "sevitab.com": "동화약품",
    # ─── User-mapped 2026-06-26 batch (긴급정정 xlsx) ─────────────
    "(주)자세샵": "자세샵",
    # ─── User-mapped 2026-06-25 batch (긴급정정 xlsx) ─────────────
    "__unverified__::더 그램 소형청소기": "에어르",
    "__unverified__::약사 설계 고불소 치약": "유어그린",
    "__unverified__::유니러브 COVA AI": "엘리프",
    "__unverified__::플릭 절충형유모차 출시": "에이원베이비",
    "__unverified__::아벤디카 헤어오일": "아벤디카",
    "__unverified__::부릉부릉 친구들": "슬립스파",
    "__unverified__::공사없이 완성하는 쇼룸": "유비스가구",
    "__unverified__::ECODION섬유탈취제": "에코디언",
    "__unverified__::프리미엄 녹는실 앰플": "유한양행",
    "__unverified__::한국동물병원협회 추천": "몽제",
    "__unverified__::멜라메이트 로우슈가구미": "CJ웰케어",
    "__unverified__::신제품 뷰아이 2세대": "필립스",
    "__unverified__::멀티비타민 맥스": "퓨어젠",
    "__unverified__::바야스던 쿨티셔츠": "컬러스튜디오",
    "__unverified__::팝케어팝스 유리너리케어": "뉴트리션트리",
    "__unverified__::비교 대상조차 없는": "사담청",
    "__unverified__::허리 편한 퀸매트리스": "모먼스트",
    "__unverified__::아이스웰 여름침대패드": "미니멀앤드",
    "__unverified__::강아지간식 개껌": "카길푸드",
    "__unverified__::허리가 편안한 몽제": "몽제",
    "__unverified__::NEW 닥터노비드 샴푸": "LG생활건강",
    "__unverified__::DB 영업용 화물차보험": "DB손해보험",
    "__unverified__::KB 영업용 화물차보험": "KB손해보험",
    "__unverified__::알집 리네브 베이비룸": "알집매트",
    "__unverified__::공학설계 리네브베이비룸": "알집매트",
    "__unverified__::심장케어 강아지 영양제": "펫생각",
    "__unverified__::맛있는 뉴트리300": "아이디얼레시피",
    "__unverified__::프리미엄 KD파마 원료": "펫생각",
    "__unverified__::키즈텐 어린이 오메가3": "키즈텐",
    "__unverified__::크루거 대형 선풍기": "네옴몰",
    "__unverified__::한양 메탈 플로어팬": "한양전자",
    "__unverified__::더 커진 용량 파티믹스": "퓨리나",
    "__unverified__::센서티비티 앤 검케어": "센소다인",
    "__unverified__::포사인콘드로이친1200": "비디피랩",
    "__unverified__::오리밤 아기베개 리뉴얼": "오리밤",
    # ─── User-mapped 2026-06-25 batch #2 (cycle 3 신규 + crtekshop) ──
    "smartstore.naver.com/crtekshop": "로지텍",
    "m.gamtanstore.com": "감탄",
    "__unverified__::Mobi Fold 출시": "로지텍",
    "__unverified__::4.7만 리뷰 진센큐": "바른뉴트리",
    "__unverified__::인견쿨 스트랩 큰컵브라": "감탄",
    # ─── User-mapped 2026-06-25 batch (긴급정정 xlsx) ─────────────
    "__unverified__::넾다세일 X 락티브": "락티브",
    "__unverified__::마이사이즈체어": "클라우드백",
    "__unverified__::처음부터 끝까지 책임감 있게!": "착한이사",
    "__unverified__::오토드진공흡착스팀다리미": "오토드",
    "__unverified__::젖병소재로 만든 샤워기": "슬로운",
    "__unverified__::베로크 세라믹 테이블": "소낭구",
    "__unverified__::바야스던 러닝 고글": "컬러스튜디오",
    "__unverified__::올케어꽉채운 수술비보험": "메리츠화재",
    "__unverified__::깨노니 쿨 출시": "종근당",
    "__unverified__::H형기갈대 트롤리PRO": "소베맘",
    "__unverified__::THE간편한건강보험": "라이나생명",
    "__unverified__::핏쳐 사이드테이블 출시": "핏쳐",
    "__unverified__::시홈 암막 수면안대": "시홈",
    "__unverified__::가온 TPE 카매트": "가온",
    "__unverified__::토들러 초극세모 칫솔": "켄트",
    "__unverified__::슬개골이 편안한 몽제": "몽제",
    "__unverified__::닥터피엘 버블세면대필터": "닥터피엘",
    "__unverified__::맑은 눈엔 비전스타": "나우케어",
    "__unverified__::익스트림 7K 에너지젤": "익스트림",
    "__unverified__::도톰 인견쿨 볼륨브라": "감탄",
    "__unverified__::대웅제약 에너씨슬집중샷": "대웅제약",
    "__unverified__::리포좀비타민C 스틱키즈": "하루틴",
    "__unverified__::NEW에어러브5 듀라론": "폴레드",
    "__unverified__::피카츄 원터치캡 빨대컵": "그린핑거",
    "__unverified__::핑거수트 물광폴리쉬": "핑거수트",
    "__unverified__::자동화장실 OPEN X": "페테토",
    "__unverified__::무본 베고나니 목쿠션": "무본",
    "__unverified__::픽셀 이지 분유쉐이커": "폴레드",
    "__unverified__::이브이 원터치캡 텀블러": "그린핑거",
    "__unverified__::구딩 베어 콧물흡입기": "구딩",
    "__unverified__::오딧세이 남성올인원로션": "오딧세이",
    "__unverified__::갤럭시ev 전기차충전기": "만땅전기차충전기",
    "__unverified__::ELT 기미크림": "이엘티코스메틱",
    "__unverified__::손목통증 전문마사지기": "미베러",
    "__unverified__::3세대 커스텀체어 6D": "누카",
    "__unverified__::이엘티 V-PDRN세럼": "이엘티코스메틱",
    "__unverified__::센서티브 건조기시트": "블랑101",
    "__unverified__::생도라지 함량 95%": "사담청",
    "__unverified__::중고차 이제 보이는게 다야, 헤이딜러": "헤이딜러",
    "__unverified__::DB손해보험다이렉트 자동차보험": "DB손해보험",
    "__unverified__::(무)라이나다이렉트치아보험Ⅱ(갱신형)": "라이나생명",
    "__unverified__::사회복지사2급 신학기 OPEN!": "바른스터디",
    "__unverified__::6년 연속 1위, 메리츠 펫보험": "메리츠화재",
    "__unverified__::린클의 모든 노하우를 담은 프라임S": "린클",
    "__unverified__::경희사이버대학교 신·편입생 모집 중": "경희사이버대학교",
    "__unverified__::동화약품 여드름 잡는 비타민": "동화약품",
    "__unverified__::NEW시리즈7 스킨쉴드": "브라운",
    "__unverified__::맞춤모션 초밀착 쉐이빙": "필립스",
    "__unverified__::U+의 가장 쉬운 통신 요금, 올인원": "LG유플러스",
    "__unverified__::우주 어드벤처가 당신을 기다립니다": "이브온라인",
    "__unverified__::오래가는염색 비겐크림톤": "동아제약",
    "__unverified__::포장이사 전문 브랜드, 로젠이사 !": "로젠이사",
    "__unverified__::디자인 경험 없이도 홈페이지 제작가능": "아임웹",
    "__unverified__::집에서 누리는 프리미엄 에스테틱": "약손명가",
    "__unverified__::펫쿠르트 왈 관절피모": "큐토펫",
    "__unverified__::MOM을 위해 맘을 다해, 콜대원키즈": "콜대원",
    "__unverified__::코너 모션 리클라이너": "모던홈즈",
    "__unverified__::계양 전동드릴 미니핏": "계양공구",
    "__unverified__::계양 미니핏 드라이버": "계양공구",
    "__unverified__::(무)AIA 원스톱종합건강보험": "AIA생명",
    "__unverified__::프랭크버거 X 정호영 셰프 에디션": "프랭크버거",
    "__unverified__::앨리스 다쳤을땐상해보험": "롯데손해보험",
    "__unverified__::운전자 상해종합보험": "메리츠화재",
    "__unverified__::여에스더 블루베리즙": "에스더포뮬러",
    "__unverified__::성공하는 사장님의 선택, 티오더": "티오더",
    "__unverified__::신상, 강아지 눈영양제": "펫생각",
    "__unverified__::강아지 눈 건강 영양제": "펫생각",
    "__unverified__::UV패턴 집업래쉬가드": "블랙야크",
    "__unverified__::전국 최저 요금제 시행": "119퀵서비스",
    "__unverified__::판매 1위 탈모치료제, 로게인 폼": "로게인",
    "__unverified__::강아지 기관지 영양제": "펫생각",
    "__unverified__::줌기능 초미니 셀카봉": "셀루미",
    "__unverified__::더마틱스리페어 스팟패치": "더마틱스",
    "__unverified__::아이스 커피 블렌드": "네슬레",
    "__unverified__::MOBI Fold": "로지텍",
    "__unverified__::느웰 천연라텍스매트리스": "느웰",
    "__unverified__::매일을 바꾸는 1포 뉴베인 붓기아웃": "뉴베인",
    "__unverified__::웹에서 만나는 밀크T 바로체험": "밀크T",
    "__unverified__::매장 효율UP 메이트 포스기 프로그램": "메이트",
    "__unverified__::장기 계약 부담 없는 패스트파이브": "패스트파이브",
    "__unverified__::메이크샵 쇼핑몰 무료 시작하기": "메이크샵",
    "__unverified__::VCT 퍼시픽 공식 모니터 벤큐 조위": "BenQ Zowie",
    "__unverified__::여성청소년의 안전한 생리기간을 위해!": "지파운데이션",
    "__unverified__::유팡맘마 PPSU 젖병": "유팡",
    "__unverified__::퓨어베이비 PA젖병": "그린핑거",
    "__unverified__::3세대 커스텀체어": "누카",
    "__unverified__::NEW S03소파 4인": "데스커",
    "__unverified__::DB 업무용 자동차보험": "DB손해보험",
    "__unverified__::KB 업무용 자동차보험": "KB손해보험",
    # ─── User-mapped 2026-05-27 batch ─────────────
    "smartstore.naver.com/aj1117": "패밀리컨셉",
    "coldaewon.co.kr": "콜대원",
    "www.coldaewon.co.kr": "콜대원",
    "m.coldaewon.co.kr": "콜대원",
    "smartstore.naver.com/_tinkerbell": "팅커벨",
    "smartstore.naver.com/foellie": "포엘리에",
    "smartstore.naver.com/into": "셀루미",
    "brand.naver.com/mayton": "메이튼",
    "taxtok.kr": "세무톡",
    "blog.naver.com": "삼성자산운용",
    "www.eveonline.com": "이브온라인",
    "eveonline.com": "이브온라인",
    "brstudy.net": "바른스터디",
    "www.1666-1646.com": "착한이사",
    "1666-1646.com": "착한이사",
    "www.sparkplus.co": "스파크플러스",
    "sparkplus.co": "스파크플러스",
    "imweb.me": "아임웹",
    # ─── 네이버 플랫폼 (path 포함) ───────────────
    "brand.naver.com/lactiv": "락티브",
    "brand.naver.com/thelittles": "더리틀즈",
    "brand.naver.com/smartcara": "스마트카라",
    "brand.naver.com/dji": "DJI",
    "brand.naver.com/peteto": "페테토",
    "brand.naver.com/camel": "카멜",
    "brand.naver.com/samdae500": "삼대오백",
    "brand.naver.com/cuchen": "쿠첸",
    "brand.naver.com/alzipmat": "알집매트",
    "brand.naver.com/aonebaby": "에이원베이비",
    "smartstore.naver.com/cottonbong": "코튼봉",
    "brand.naver.com/cottonbong": "코튼봉",
    "brand.naver.com/dermafirm": "더마펌",
    "brand.naver.com/koreaeundanhc": "고려은단",
    "brand.naver.com/airr": "에이르",
    "brand.naver.com/biteme1": "바잇미",
    "brand.naver.com/cj_wellcare": "CJ웰케어",
    "brand.naver.com/cloudback": "클라우드백",
    "brand.naver.com/cozyma": "코지마",
    "brand.naver.com/gaoncarmat": "가온카매트",
    "brand.naver.com/greenfingerstore": "그린핑거",
    "brand.naver.com/passene": "파센느",
    "brand.naver.com/wangta": "왕타",
    "smartstore.naver.com/77mile": "레인스카이",
    "smartstore.naver.com/actytoe": "액티토",
    "smartstore.naver.com/coody": "쿠디",
    "smartstore.naver.com/curadle": "큐레이들",
    "smartstore.naver.com/denable": "디네이블",
    "smartstore.naver.com/ggumang": "꾸망",
    "smartstore.naver.com/jonrkr": "존알",
    "smartstore.naver.com/medi_info": "메디인포",
    "smartstore.naver.com/payhere": "페이히어",
    "smartstore.naver.com/tkeka": "사담청",
    "smartstore.naver.com/umgong": "엄공",
    # ─── 2nd batch (brand.naver.com) ─────────────
    "brand.naver.com/dr_lean": "닥터린",
    "brand.naver.com/poled": "폴레드",
    "brand.naver.com/bodydoctors": "바디닥터스",
    "brand.naver.com/cuckoo": "쿠쿠",
    "brand.naver.com/kklizen": "끌리젠",
    "brand.naver.com/thinkpets": "펫생각",
    "brand.naver.com/aghealth": "안국건강",
    "brand.naver.com/braun": "브라운",
    "brand.naver.com/chongkundang": "종근당",
    "brand.naver.com/fromb": "프롬비",
    "brand.naver.com/karnik": "카르닉",
    "brand.naver.com/philips": "필립스",
    "brand.naver.com/adornshop": "아던샵",
    "brand.naver.com/bang-olufsen": "뱅앤올룹슨",
    "brand.naver.com/bareunnutri": "바른뉴트리",
    "brand.naver.com/baruner": "바르너",
    "brand.naver.com/brgoggan": "반려곳간",
    "brand.naver.com/centellian24": "센텔리안24",
    "brand.naver.com/dalelaf": "달리프",
    "brand.naver.com/dibea": "디베아",
    "brand.naver.com/fiture": "핏체",
    "brand.naver.com/grainon": "그레인온",
    "brand.naver.com/handok": "한독헬스케어",
    "brand.naver.com/healthhelper": "헬스헬퍼",
    "brand.naver.com/inavi": "아이나비",
    "brand.naver.com/kenvueofficial": "켄뷰",
    "brand.naver.com/malanghoney": "말랑하니",
    "brand.naver.com/momenst": "모먼스트",
    "brand.naver.com/nooka": "누카",
    "brand.naver.com/novita_official": "노비타",
    "brand.naver.com/nutrione": "뉴트리원",
    "brand.naver.com/pamperskr": "팸퍼스",
    "brand.naver.com/pepemall": "페페몰",
    "brand.naver.com/runwalk": "런워크",
    "brand.naver.com/sollie": "솔리에",
    "brand.naver.com/taomi": "타오미",
    "brand.naver.com/vetple": "벳플",
    "brand.naver.com/wlckorea": "웰스로만센트라린",
    "brand.naver.com/yupbaby": "와이업",
    # ─── 2nd batch (smartstore.naver.com) ────────
    "smartstore.naver.com/brushup": "브러쉬업",
    "smartstore.naver.com/foreun": "포른",
    "smartstore.naver.com/reflowofficial": "리플로우",
    "smartstore.naver.com/6aoc": "육아원칙",
    "smartstore.naver.com/acessaks": "에이스전자",
    "smartstore.naver.com/buddykorea": "버디라이프",
    "smartstore.naver.com/cheonsewon": "천세원",
    "smartstore.naver.com/cleanwow": "클린와우",
    "smartstore.naver.com/ecodion": "에코디언",
    "smartstore.naver.com/endpuff": "엔드퍼프",
    "smartstore.naver.com/gssys": "만땅",
    "smartstore.naver.com/hae-ol": "해올",
    "smartstore.naver.com/henkel_beauty": "헨켈뷰티",
    "smartstore.naver.com/hielpos": "히엘페이",
    "smartstore.naver.com/iwant_hlbls": "아이원트",
    "smartstore.naver.com/kucham": "쿠참",
    "smartstore.naver.com/martincarat": "마틴캐럿",
    "smartstore.naver.com/neommall": "네옴몰",
    "smartstore.naver.com/pazzyhome": "파찌홈",
    "smartstore.naver.com/philipsmassage": "필립스",
    "smartstore.naver.com/pickfrom_": "픽프롬",
    "smartstore.naver.com/qaidmall": "큐에이드",
    "smartstore.naver.com/richliebe": "둥절",
    "smartstore.naver.com/ruhens": "루헨스",
    "smartstore.naver.com/teenature": "티네이처",
    "smartstore.naver.com/thankswalnut": "땡스월넛",
    "smartstore.naver.com/thekbbio": "바이탈타임",
    "smartstore.naver.com/tpay": "오케이포스",
    "smartstore.naver.com/vilarstore": "빌라르",
    "smartstore.naver.com/wonangsink": "원앙싱크",
    "smartstore.naver.com/wooelt": "코엘스",
    # ─── 3rd batch (brand.naver.com) ─────────────
    "brand.naver.com/kgcshop": "정관장",
    "brand.naver.com/hanyang_1998": "한양테크",
    "brand.naver.com/minimaland": "미니멀앤드",
    "brand.naver.com/sensodyne": "센소다인",
    "brand.naver.com/beready": "비레디",
    "brand.naver.com/blancnature": "블랑네이처",
    "brand.naver.com/by_lab": "바이랩",
    "brand.naver.com/caddytalk": "캐디톡",
    "brand.naver.com/cozymohae": "코지모해",
    "brand.naver.com/daewonhealth": "대원헬스",
    "brand.naver.com/dapharm": "동아제약",
    "brand.naver.com/dermatix": "더마틱스",
    "brand.naver.com/desimone": "드시모네",
    "brand.naver.com/desker": "데스커",
    "brand.naver.com/dr_phyto": "닥터파이토",
    "brand.naver.com/drfelis": "닥터펠리스",
    "brand.naver.com/erhana": "이알하나",
    "brand.naver.com/haenim": "해님",
    "brand.naver.com/home-art": "홈앤아트",
    "brand.naver.com/kanu": "카누",
    "brand.naver.com/kellogg": "켈로그",
    "brand.naver.com/kent": "켄트",
    "brand.naver.com/kormat": "고려화학매트",
    "brand.naver.com/lameda": "라메다",
    "brand.naver.com/meliens": "멜리언스",
    "brand.naver.com/naturedream": "네이처드림",
    "brand.naver.com/neworigin": "뉴오리진",
    "brand.naver.com/nutricore": "뉴트리코어",
    "brand.naver.com/oastore": "오아",
    "brand.naver.com/sensemom": "센스맘",
    "brand.naver.com/sleepspa": "슬립스파",
    "brand.naver.com/sonicare": "필립스 소닉케어",
    "brand.naver.com/upangkorea": "유팡",
    "brand.naver.com/winixshow": "위닉스",
    # ─── 3rd batch (smartstore.naver.com) ────────
    "smartstore.naver.com/bebeskin": "베베스킨",
    "smartstore.naver.com/by_laugh": "라프",
    "smartstore.naver.com/each_un": "이치언리븐",
    "smartstore.naver.com/leadersnote": "더리더스노트",
    "smartstore.naver.com/libox": "라이브박스",
    "smartstore.naver.com/look_goods": "이너띵스",
    "smartstore.naver.com/nature": "동성제약",
    "smartstore.naver.com/nucgalaxy": "엔유씨",
    "smartstore.naver.com/oneofthem-official": "원오브뎀",
    "smartstore.naver.com/sleepillow": "슬리필로우",
    "smartstore.naver.com/snughome": "스너그홈",
    "smartstore.naver.com/sonangumusee": "소낭구뮤제",
    "smartstore.naver.com/sound_bone": "사운드본",
    "smartstore.naver.com/vivisshop": "모즈스웨덴",
    # ─── 4th batch (Naver platform — 사용자 명시 2026-06-09) ─────
    "brand.naver.com/lgcaremall": "LG생활건강",
    "brand.naver.com/haroutine": "하루틴",
    "brand.naver.com/cargillpetfood": "카길펫푸드",
    "smartstore.naver.com/houssen": "휴렉",
    "brand.naver.com/dapharmpersonalcare": "동아제약",
    "brand.naver.com/centrum": "센트룸",
    "smartstore.naver.com/hyoja09mall": "효자",
    "brand.naver.com/finevu": "파인뷰",
    "smartstore.naver.com/havacam": "해바캄",
    "smartstore.naver.com/mediaid_kr": "메디에이드",
    "brand.naver.com/orte": "오르테",
    "brand.naver.com/mommydaddy": "마미앤대디",
    "brand.naver.com/selex": "셀렉스",
    "brand.naver.com/namyang": "남양유업",
    "brand.naver.com/mamypokostore": "마미포코",
    "brand.naver.com/belkinstore": "벨킨",
    "brand.naver.com/c2mnew": "씨투엠뉴",
    "bbongbra.co.kr": "뽕브라몰",
    "www.bbongbra.co.kr": "뽕브라몰",
    "m.bbongbra.co.kr": "뽕브라몰",
    "epsonlounge.co.kr": "엡손",
    "www.epsonlounge.co.kr": "엡손",
    "m.epsonlounge.co.kr": "엡손",
    "thebenefood.co.kr": "더베네푸드",
    "www.thebenefood.co.kr": "더베네푸드",
    "m.thebenefood.co.kr": "더베네푸드",
    "yuhanclorox.com": "유한클로락스",
    "www.yuhanclorox.com": "유한클로락스",
    "m.yuhanclorox.com": "유한클로락스",
    "sirbot.kr": "써봇",
    "www.sirbot.kr": "써봇",
    "m.sirbot.kr": "써봇",
    "fastfive.co.kr": "패스트파이브",
    "www.fastfive.co.kr": "패스트파이브",
    "m.fastfive.co.kr": "패스트파이브",
    # ─── 5th batch (사용자 확인 정상 매핑 — 휴리스틱 의존 제거) ──
    "puliodays.com": "풀리오",
    "www.puliodays.com": "풀리오",
    "m.puliodays.com": "풀리오",
    "easydew.co.kr": "이지듀",
    "www.easydew.co.kr": "이지듀",
    "m.easydew.co.kr": "이지듀",
    "titad.kr": "티타드",
    "www.titad.kr": "티타드",
    "m.titad.kr": "티타드",
    "alvins.co.kr": "엘빈즈",
    "www.alvins.co.kr": "엘빈즈",
    "m.alvins.co.kr": "엘빈즈",
    "spa-r.com": "스파알",
    "www.spa-r.com": "스파알",
    "m.spa-r.com": "스파알",
    "ssoook.co.kr": "쏘오옥",
    "www.ssoook.co.kr": "쏘오옥",
    "m.ssoook.co.kr": "쏘오옥",
    "oldernew.kr": "올더뮤",
    "www.oldernew.kr": "올더뮤",
    "m.oldernew.kr": "올더뮤",
    "vuca.co.kr": "뷰카",
    "www.vuca.co.kr": "뷰카",
    "m.vuca.co.kr": "뷰카",
    "youngranu.co.kr": "영라뉴",
    "www.youngranu.co.kr": "영라뉴",
    "m.youngranu.co.kr": "영라뉴",
    "krhuaweidevice.com": "화웨이",
    "www.krhuaweidevice.com": "화웨이",
    "m.krhuaweidevice.com": "화웨이",
    "renfit.co.kr": "리앤핏",
    "www.renfit.co.kr": "리앤핏",
    "m.renfit.co.kr": "리앤핏",
    "navienhouse.com": "나비엔",
    "www.navienhouse.com": "나비엔",
    "m.navienhouse.com": "나비엔",
    "ollocdam.com": "올록담",
    "www.ollocdam.com": "올록담",
    "m.ollocdam.com": "올록담",
    "godbody.co.kr": "갓바디",
    "www.godbody.co.kr": "갓바디",
    "m.godbody.co.kr": "갓바디",
    "cruntin.com": "크런틴",
    "www.cruntin.com": "크런틴",
    "m.cruntin.com": "크런틴",
    "brand.naver.com/dentistekorea": "덴티스테",
    # ─── 6th batch (사용자 확인 매핑 2026-06-22) ────
    "brand.naver.com/dasoda": "다소다",
    "brand.naver.com/reencle": "린클",
    "brand.naver.com/otokimall": "오뚜기",
    "brand.naver.com/yaksonmall": "하은누리",
    "brand.naver.com/agaand": "아가앤",
    "brand.naver.com/age20s": "에이지투웨니스",
    "brand.naver.com/ainhealthcare": "아인헬스케어",
    # 사운드판다는 광고 카피 "AI이어폰SPE-G11"이 display로 잡힘 — host 매핑 +
    # DISPLAY_FULL_CANONICAL 양쪽 모두 등록.
    "soundpanda.co.kr": "사운드판다",
    "www.soundpanda.co.kr": "사운드판다",
    "m.soundpanda.co.kr": "사운드판다",
    "brand.naver.com/ascent": "에이센트",
    "brand.naver.com/asus": "ASUS",
    "brand.naver.com/ateen_seoul": "재피렉스",
    "brand.naver.com/bambulabkr": "뱀부랩",
    "brand.naver.com/basixm": "디큐브",
    "brand.naver.com/bebesup": "베베숲",
    "brand.naver.com/bellagarden": "벨라가든",
    "brand.naver.com/beolmoon": "벌문",
    "brand.naver.com/biopets": "바이오펫츠",
    "brand.naver.com/blaupunkt": "블라우풍트",
    "brand.naver.com/bluefeel": "블루필",
    "brand.naver.com/bn3335": "몽쿨",
    "brand.naver.com/bnrmall": "비에날",
    "brand.naver.com/bodyand": "바디앤",
    "brand.naver.com/calmto": "캄토",
    # smartstore.naver.com 변형 (사용자가 슬러그만 준 케이스 — 두 host 형식 모두 등록)
    "smartstore.naver.com/agaand": "아가앤",
    "smartstore.naver.com/age20s": "에이지투웨니스",
    "smartstore.naver.com/ainhealthcare": "아인헬스케어",
    "smartstore.naver.com/ascent": "에이센트",
    "smartstore.naver.com/asus": "ASUS",
    "smartstore.naver.com/ateen_seoul": "재피렉스",
    "smartstore.naver.com/bambulabkr": "뱀부랩",
    "smartstore.naver.com/basixm": "디큐브",
    "smartstore.naver.com/bebesup": "베베숲",
    "smartstore.naver.com/bellagarden": "벨라가든",
    "smartstore.naver.com/bellagarden_": "벨라가든",
    "smartstore.naver.com/beolmoon": "벌문",
    "smartstore.naver.com/biopets": "바이오펫츠",
    "smartstore.naver.com/blaupunkt": "블라우풍트",
    "smartstore.naver.com/bluefeel": "블루필",
    "smartstore.naver.com/bn3335": "몽쿨",
    "smartstore.naver.com/bnrmall": "비에날",
    "smartstore.naver.com/bodyand": "바디앤",
    "smartstore.naver.com/calmto": "캄토",
    # 이전 batch도 smartstore 변형 누락분 보강
    "smartstore.naver.com/dasoda": "다소다",
    "smartstore.naver.com/reencle": "린클",
    "smartstore.naver.com/otokimall": "오뚜기",
    "smartstore.naver.com/yaksonmall": "하은누리",
    "themedicube.co.kr": "메디큐브",
    "www.themedicube.co.kr": "메디큐브",
    "m.themedicube.co.kr": "메디큐브",
    "bullsonemall.com": "불스원",
    "www.bullsonemall.com": "불스원",
    "m.bullsonemall.com": "불스원",
    "byn.kr": "블랙야크",
    "www.byn.kr": "블랙야크",
    "m.byn.kr": "블랙야크",
    "cartier.com": "까르띠에",
    "www.cartier.com": "까르띠에",
    "m.cartier.com": "까르띠에",
    "allforcat.co.kr": "올포캣",
    "www.allforcat.co.kr": "올포캣",
    "m.allforcat.co.kr": "올포캣",
    "kr.store.bambulab.com": "밤부랩",
    "store.bambulab.com": "밤부랩",
    "bambulab.com": "밤부랩",
    "www.bambulab.com": "밤부랩",
}


# Display-name overrides for cases where Stage 2 couldn't resolve a host
# but the heuristic guess from ad copy is known to be wrong.
#
# When `canonical_brand_name(host, display)` would otherwise fall through to
# guess_from_display, this map is consulted FIRST. If the display's first
# token matches a key here, the value is returned as the canonical brand.
#
# Add an entry whenever the brand-cleanup dashboard surfaces a wrong
# display (e.g. 'Pro+' should really be '헤이홈'). Run
# `scripts/reconcile_brands.py` after editing to apply to existing rows.
DISPLAY_CANONICAL: dict[str, str] = {
    "뻬를리": "반클리프아펠",      # → www.vancleefarpels.com
    "Qrevo": "로보락",             # → kr.roborock.com
    "Pro+": "헤이홈",              # → www.hej.life
    "강력한": "발렌",              # → bodranmall.com
    "에스클래스": "위바이옴",       # → webiommall.co.kr
    "굿앤굿": "현대해상",          # 굿앤굿 어린이종합보험Q (현대해상 상품) → hi.co.kr 변형
    "굿앳굿": "현대해상",          # '굿앤굿' 발음 오타 변형 안전망
}


# Full ad-copy → canonical brand. Checked BEFORE DISPLAY_CANONICAL and
# guess_from_display. Use this when the first word would over-match
# unrelated ads (e.g. "현장의" appears in many ad copies but the exact
# phrase "현장의 신뢰를 기록하다!" only ever belongs to 포팩트).
#
# Add an entry whenever the brand-cleanup dashboard surfaces a wrong
# brand whose first word is too generic to safely add to DISPLAY_CANONICAL.
DISPLAY_FULL_CANONICAL: dict[str, str] = {
    "현장의 신뢰를 기록하다!": "포팩트",   # → www.4fact.co.kr
    "입냄새 바로 셧다운!": "덴티스테",     # → brand.naver.com/dentistekorea
    "AI이어폰SPE-G11": "사운드판다",       # → soundpanda.co.kr
    "한화더경증간편건강보험Ⅱ": "한화손해보험",  # → hwgi.kr
}


# Tokens that aren't real brand words (prefixes, qualifiers) we trim.
_NOISE_PREFIXES = ("(무)", "(유)", "(주)", "[", "<")
_NOISE_REGEX = re.compile(r"^[\s\W]+")

# First-word tokens that are NEVER brand names — when an ad copy starts with
# one of these, the heuristic should give up rather than guess incorrectly.
_NON_BRAND_FIRST_WORDS = {
    # Generic qualifiers / adjectives
    "고함량", "고용량", "초고함량", "프리미엄", "최고급", "특가", "신상", "신제품",
    "공식", "정품", "정식", "한정", "한정판", "선착순", "행사", "할인",
    "오늘", "지금", "당일", "단독", "단하루", "단7일", "단7일만",
    "하루에", "매일", "매주", "오늘만", "주말", "이번주", "이번달",
    "전국", "국내", "해외", "글로벌",
    "판매", "구매", "주문", "결제", "배송",
    # Numbers/ranks
    "1위", "2위", "3위", "TOP1", "TOP", "NO1", "NO.1",
    # Generic nouns
    "건강", "선물", "이벤트", "쿠폰", "사은품",
    "더", "더욱", "가장", "최고", "최상", "최초", "최신",
    "신청", "후기", "리뷰",
    # English noise
    "NEW", "BEST", "HOT", "SALE", "FREE",
    # Korean particles/conjunctions
    "이", "그", "저", "이게", "그게", "이런", "그런", "이번",
    "처음부터", "끝까지", "성장", "성능",
    # Other observed noise
    "사회복지사", "사회복지사2급", "디자인", "주식회사", "휴대폰",
    "포장이사", "건강하게", "이가격에", "3일", "손목통증", "여에스더글루타치온",
    "보험", "보장", "건강보험",
    # Postpositional phrases / generic nouns that ad copy commonly leads with
    "웹에서", "학점은행제", "학점은행", "사이버대학교", "사이버대학",
    # The placeholder "(미확인 브랜드)" sentinel must never round-trip back
    # into a real brand identity. Block both the prefix-stripped first word
    # and any other obvious variants.
    "미확인", "현장의", "FORWEB",
}


def guess_from_display(display_name: str | None) -> str | None:
    """Heuristic fallback: pull the first word of the ad copy as the brand.

    Examples:
      "삼성화재 다이렉트 실손의료비보험" → "삼성화재"
      "라이나 첫날부터암보험"            → "라이나"
      "(무)AIA 원스톱종합건강보험"       → "AIA"

    Returns None if input is empty OR if the first word is a known non-brand
    qualifier — in that case the caller should fall back to the full ad copy
    or treat the brand as unknown.
    """
    if not display_name:
        return None
    text = display_name.strip()
    # Strip leading noise like "(무)" / brackets
    for p in _NOISE_PREFIXES:
        if text.startswith(p):
            text = text[len(p):].lstrip()
    text = _NOISE_REGEX.sub("", text)
    if not text:
        return None
    # First whitespace-delimited token, but keep "KB손해보험" etc. as a unit.
    first = text.split()[0] if text.split() else ""
    if not first:
        return None
    if first in _NON_BRAND_FIRST_WORDS:
        return None
    return first


def canonical_brand_name(host: str | None, display_name: str | None) -> str | None:
    """Return canonical brand name with this priority:

    1. Exact match in HOST_TO_BRAND (e.g. "direct.samsungfire.com" → "삼성화재",
       "brand.naver.com/lactiv" → "락티브").
    2. For Naver-platform hosts (`brand.naver.com/X`, `smartstore.naver.com/X`)
       not in HOST_TO_BRAND, use the path segment itself (X) as the brand
       identifier — this is the Naver brand store's slug, which is far more
       reliable than the first word of the ad copy.
    3. DISPLAY_CANONICAL override — known-wrong heuristic guesses
       (e.g. "Pro+" → "헤이홈") get corrected here.
    4. First-word heuristic of the ad copy (filtered by non-brand blocklist).

    Returns None if no canonical name can be determined.
    """
    if host and host in HOST_TO_BRAND:
        return HOST_TO_BRAND[host]
    # Platform host with path segment → use the slug (e.g. "peteto", "camel")
    if host and "/" in host:
        h_base, _, seg = host.partition("/")
        if h_base in PLATFORM_HOSTS and seg:
            return seg
    # Full ad-copy match (strongest display-side signal — exact-phrase only).
    if display_name:
        stripped = display_name.strip()
        if stripped in DISPLAY_FULL_CANONICAL:
            return DISPLAY_FULL_CANONICAL[stripped]
    # First-word override — catches known-wrong heuristic guesses like
    # "뻬를리", "Qrevo", "Pro+", "강력한", "에스클래스".
    if display_name:
        first = display_name.strip().split()[0] if display_name.strip().split() else ""
        if first in DISPLAY_CANONICAL:
            return DISPLAY_CANONICAL[first]
    return guess_from_display(display_name)
