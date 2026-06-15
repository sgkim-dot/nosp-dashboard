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
    "theleadersnote.com": "더 리더스 노트",
    "www.theleadersnote.com": "더 리더스 노트",
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
    "www.hwgi.kr": "한화생명",
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
    # ─── User-mapped 2026-05-27 batch ─────────────
    "smartstore.naver.com/aj1117": "패밀리컨셉",
    "www.coldaewon.co.kr": "콜대원",
    "smartstore.naver.com/_tinkerbell": "팅커벨",
    "smartstore.naver.com/foellie": "포엘리에",
    "smartstore.naver.com/into": "셀루미",
    "brand.naver.com/mayton": "메이튼",
    "taxtok.kr": "세무톡",
    "blog.naver.com": "삼성자산운용",
    "www.eveonline.com": "이브온라인",
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
