#!/usr/bin/env python3
"""
Conference Deadline Alert Bot v6
학회별로 그룹화, 모든 deadline을 하위 항목으로 표시
"""

import requests
import json
import yaml
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# ccfddl에서 가져올 학회 목록 (카테고리/파일명)
CCFDDL_CONFERENCES = [
    # AI - ML/Vision
    ("AI", "cvpr"),
    ("AI", "iccv"),
    ("AI", "eccv"),
    ("AI", "aaai"),
    ("AI", "ijcai"),
    ("AI", "icml"),
    ("AI", "nips"),  # NeurIPS
    ("AI", "iclr"),
    ("AI", "aistats"),
    ("AI", "colt"),
    ("AI", "uai"),
    ("AI", "accv"),
    ("AI", "bmvc"),
    ("AI", "wacv"),
    ("AI", "icpr"),
    # AI - NLP
    ("AI", "acl"),
    ("AI", "emnlp"),
    ("AI", "naacl"),
    ("AI", "eacl"),
    ("AI", "coling"),
    ("AI", "conll"),
    ("AI", "ijcnlp"),
    # AI - 기타 (에이전트/계획/진화)
    ("AI", "aamas"),
    ("AI", "ecai"),
    ("AI", "icaps"),
    ("AI", "kr"),
    ("AI", "gecco"),
    # AI - Robotics
    ("AI", "icra"),
    ("AI", "iros"),
    ("AI", "rss"),
    ("AI", "corl"),
    # AI - 학제간 (ccfddl에서는 MX 카테고리)
    ("MX", "miccai"),
    ("MX", "mlsys"),
    # Security
    ("SC", "sp"),      # IEEE S&P
    ("SC", "ccs"),
    ("SC", "uss"),     # USENIX Security
    ("SC", "ndss"),
    ("SC", "esorics"),
    ("SC", "dsn"),
    ("SC", "asiaccs"),
    ("SC", "acsac"),
    ("SC", "raid"),
    ("SC", "eurosp"),  # EuroS&P
    ("SC", "csfw"),    # CSF
    ("SC", "codaspy"),
    ("SC", "soups"),
    ("SC", "pets"),    # PETS/PoPETs
    ("SC", "wisec"),
    ("SC", "sec"),     # IFIP SEC
    # Crypto
    ("SC", "eurocrypt"),
    ("SC", "crypto"),
    ("SC", "asiacrypt"),
    ("SC", "ches"),    # CHES/TCHES
    ("SC", "acns"),
    ("SC", "fc"),      # Financial Cryptography
    ("SC", "pkc"),
    ("SC", "tcc"),
    ("SC", "fse"),     # Fast Software Encryption
    # Network
    ("NW", "sigcomm"),
    ("NW", "infocom"),
    ("NW", "nsdi"),
    ("DS", "sigmetrics"),
    # Data
    ("DB", "icdm"),
    ("MX", "bigdata"),
]

CATEGORY_MAP = {
    "AI": "AI/Vision",
    "SC": "Security",
    "NW": "Network",
    "DS": "Network",
    "DB": "Data",
    "SE": "Software",
    "MX": "AI/Vision",  # miccai, mlsys
}

# 개별 학회 카테고리 오버라이드 (sub 기본 매핑과 다른 경우)
CATEGORY_OVERRIDE = {
    ("MX", "bigdata"): "Data",
}

# 목표 학회 (짝수일에 표시) - ccfddl title 기준 정확한 이름
TARGET_CONFERENCES = [
    "CHES",            # CHES/TCHES
    "EUROCRYPT",
    "ASIACRYPT",
    "USENIX Security",
    "S&P",             # IEEE S&P
    "AsiaCCS",
]

# 타임존 매핑 (ccfddl 형식 -> IANA 형식)
TIMEZONE_MAP = {
    "UTC-12": "Etc/GMT+12",  # AoE (Anywhere on Earth)
    "AoE": "Etc/GMT+12",
    "UTC-11": "Etc/GMT+11",
    "UTC-10": "Etc/GMT+10",
    "UTC-9": "Etc/GMT+9",
    "UTC-8": "Etc/GMT+8",   # PST
    "UTC-7": "Etc/GMT+7",   # PDT
    "UTC-6": "Etc/GMT+6",
    "UTC-5": "Etc/GMT+5",   # EST
    "UTC-4": "Etc/GMT+4",
    "UTC-3": "Etc/GMT+3",
    "UTC-2": "Etc/GMT+2",
    "UTC-1": "Etc/GMT+1",
    "UTC": "UTC",
    "UTC+0": "UTC",
    "UTC+1": "Etc/GMT-1",
    "UTC+2": "Etc/GMT-2",
    "UTC+3": "Etc/GMT-3",
    "UTC+4": "Etc/GMT-4",
    "UTC+5": "Etc/GMT-5",
    "UTC+6": "Etc/GMT-6",
    "UTC+7": "Etc/GMT-7",
    "UTC+8": "Etc/GMT-8",   # CST (China)
    "UTC+9": "Etc/GMT-9",   # KST
    "UTC+10": "Etc/GMT-10",
    "UTC+11": "Etc/GMT-11",
    "UTC+12": "Etc/GMT-12",
}

KST = ZoneInfo("Asia/Seoul")


def convert_to_kst(deadline, timezone_str):
    """deadline을 해당 타임존에서 KST로 변환"""
    # 타임존 매핑
    tz_str = TIMEZONE_MAP.get(timezone_str, "Etc/GMT+12")  # 기본값 AoE
    
    try:
        tz = ZoneInfo(tz_str)
    except:
        tz = ZoneInfo("Etc/GMT+12")
    
    # deadline에 타임존 부여
    deadline_with_tz = deadline.replace(tzinfo=tz)
    
    # KST로 변환
    deadline_kst = deadline_with_tz.astimezone(KST)
    
    return deadline_kst


def fetch_ccfddl_conference(sub, name):
    """ccfddl GitHub에서 개별 학회 YAML 가져오기"""
    url = f"https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/{sub}/{name}.yml"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return yaml.safe_load(response.text)
    except Exception as e:
        print(f"[ccfddl] Error fetching {sub}/{name}: {e}")
    
    return None


def parse_deadline(deadline_str):
    """데드라인 문자열 파싱"""
    if not deadline_str:
        return None
    
    clean_str = str(deadline_str).strip().replace("'", "").replace('"', '')
    
    if any(x in clean_str.upper() for x in ["TBD", "TBA", "N/A"]):
        return None
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    
    return None


def collect_conferences():
    """ccfddl에서 학회 정보 수집 - 학회별로 그룹화"""
    conferences = []
    
    for sub, name in CCFDDL_CONFERENCES:
        data = fetch_ccfddl_conference(sub, name)
        if not data:
            continue
        
        for conf in data:
            title = conf.get('title', '')
            description = conf.get('description', '')
            rank = conf.get('rank', {}).get('ccf', '')
            
            for cycle in conf.get('confs', []):
                year = cycle.get('year', '')
                link = cycle.get('link', '')
                place = cycle.get('place', 'TBA')
                date = cycle.get('date', 'TBA')
                timezone = cycle.get('timezone', 'UTC-12')
                
                # 모든 timeline을 하나의 리스트로
                timelines = []
                for t in cycle.get('timeline', []):
                    comment = t.get('comment', '')
                    
                    # Abstract deadline
                    abstract_str = t.get('abstract_deadline')
                    abstract_date = parse_deadline(abstract_str)
                    if abstract_date:
                        abstract_kst = convert_to_kst(abstract_date, timezone)
                        timelines.append({
                            'type': 'Abstract Registration',
                            'deadline': abstract_date,
                            'deadline_kst': abstract_kst,
                            'comment': comment
                        })
                    
                    # Paper deadline
                    paper_str = t.get('deadline')
                    paper_date = parse_deadline(paper_str)
                    if paper_date:
                        paper_kst = convert_to_kst(paper_date, timezone)
                        timelines.append({
                            'type': 'Paper Submission',
                            'deadline': paper_date,
                            'deadline_kst': paper_kst,
                            'comment': comment
                        })
                
                if timelines:
                    conferences.append({
                        'name': title,
                        'full_name': description,
                        'category': CATEGORY_OVERRIDE.get((sub, name), CATEGORY_MAP.get(sub, sub)),
                        'ccf_rank': rank,
                        'year': year,
                        'place': place,
                        'date': date,
                        'timezone': timezone,
                        'link': link,
                        'timelines': timelines,
                        'source': 'ccfddl'
                    })
        
        print(f"[ccfddl] Fetched {sub}/{name}")
    
    return conferences


def get_upcoming_conferences(conferences):
    """현재 연도 + 다음 연도까지의 학회 필터링"""
    now_kst = datetime.now(KST)
    current_year = now_kst.year
    next_year = current_year + 1
    upcoming = []
    
    for conf in conferences:
        # 각 timeline의 days_left 계산 (KST 기준)
        future_timelines = []
        min_days_left = float('inf')
        
        for t in conf['timelines']:
            deadline_kst = t['deadline_kst']
            days_left = (deadline_kst - now_kst).days
            
            # 미래 deadline만 포함, 현재/다음 연도만
            if days_left >= 0 and deadline_kst.year <= next_year:
                t['days_left'] = days_left
                future_timelines.append(t)
                min_days_left = min(min_days_left, days_left)
        
        if future_timelines:
            conf['timelines'] = sorted(future_timelines, key=lambda x: x['deadline_kst'])
            conf['min_days_left'] = min_days_left
            upcoming.append(conf)
    
    # 가장 빠른 deadline 기준 정렬
    upcoming.sort(key=lambda x: x['min_days_left'])
    return upcoming


def filter_target_conferences(conferences):
    """목표 학회만 필터링"""
    target_names = {t.upper() for t in TARGET_CONFERENCES}
    return [conf for conf in conferences if conf['name'].upper() in target_names]


def format_slack_message_by_category(conferences):
    """Slack 메시지 포맷팅 - 분야별 그룹화 (홀수일용)"""
    current_year = datetime.now().year

    if not conferences:
        return {
            "text": f"📅 *Conference Deadline Alert*\n\n{current_year}-{current_year+1} 예정된 학회 데드라인이 없습니다."
        }

    # 분야별 분류
    by_category = {}
    for conf in conferences:
        cat = conf['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(conf)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📅 Conference Deadline Alert (분야별)",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{current_year}-{current_year+1} 총 {len(conferences)}개 학회* | 분야: {', '.join(by_category.keys())}"
            }
        },
        {"type": "divider"}
    ]

    def get_urgency_emoji(days_left):
        if days_left <= 30:
            return "🔴"
        elif days_left <= 180:
            return "🟡"
        else:
            return "🟢"

    def format_conference(conf):
        emoji = get_urgency_emoji(conf['min_days_left'])

        if conf.get('link'):
            conf_name = f"<{conf['link']}|{conf['name']} {conf['year']}>"
        else:
            conf_name = f"{conf['name']} {conf['year']}"

        rank_info = f" (CCF-{conf['ccf_rank']})" if conf.get('ccf_rank') else ""

        lines = [f"{emoji} *{conf_name}*{rank_info}"]
        lines.append(f"     📍 {conf['place']} | 🗓️ {conf['date']}")

        for t in conf['timelines']:
            kst_str = t['deadline_kst'].strftime('%Y-%m-%d %H:%M')
            comment = f" ({t['comment']})" if t['comment'] else ""
            lines.append(f"     • {t['type']}: {kst_str} KST (D-{t['days_left']}){comment}")

        return "\n".join(lines)

    # 분야별로 출력
    category_order = ["Security", "AI/Vision", "Network", "Data", "Software"]
    for cat in category_order:
        if cat not in by_category:
            continue

        conf_list = sorted(by_category[cat], key=lambda x: x['min_days_left'])

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📁 {cat} ({len(conf_list)}개)*"
            }
        })

        for conf in conf_list:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_conference(conf)}
            })

        blocks.append({"type": "divider"})

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST | Source: ccfddl"
            }
        ]
    })

    return {"blocks": blocks}


def format_slack_message_target(conferences):
    """Slack 메시지 포맷팅 - 목표 학회용 (짝수일용)"""
    current_year = datetime.now().year

    if not conferences:
        return {
            "text": f"🎯 *Target Conference Alert*\n\n{current_year}-{current_year+1} 목표 학회 데드라인이 없습니다."
        }

    # 기간별 분류
    urgent = [c for c in conferences if c['min_days_left'] <= 30]
    upcoming = [c for c in conferences if 30 < c['min_days_left'] <= 180]
    later = [c for c in conferences if c['min_days_left'] > 180]

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🎯 Target Conference Alert",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*목표 학회*: {', '.join(TARGET_CONFERENCES)}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔴 긴급 (30일내): {len(urgent)}  |  🟡 임박 (6개월내): {len(upcoming)}  |  🟢 여유 (6개월+): {len(later)}"
            }
        },
        {"type": "divider"}
    ]

    def get_urgency_emoji(days_left):
        if days_left <= 30:
            return "🔴"
        elif days_left <= 180:
            return "🟡"
        else:
            return "🟢"

    def format_conference(conf):
        emoji = get_urgency_emoji(conf['min_days_left'])

        if conf.get('link'):
            conf_name = f"<{conf['link']}|{conf['name']} {conf['year']}>"
        else:
            conf_name = f"{conf['name']} {conf['year']}"

        rank_info = f" (CCF-{conf['ccf_rank']})" if conf.get('ccf_rank') else ""

        lines = [f"{emoji} *{conf_name}*{rank_info}"]
        lines.append(f"     📍 {conf['place']}")
        lines.append(f"     🗓️ {conf['date']}")
        lines.append(f"     🕐 {conf.get('timezone', 'UTC-12')}")

        for t in conf['timelines']:
            orig_str = t['deadline'].strftime('%Y-%m-%d %H:%M')
            kst_str = t['deadline_kst'].strftime('%Y-%m-%d %H:%M')
            comment = f" ({t['comment']})" if t['comment'] else ""
            lines.append(f"     • {t['type']}: {kst_str} KST (D-{t['days_left']}) / {orig_str} {conf.get('timezone', '')}{comment}")

        return "\n".join(lines)

    def add_section(title, conf_list):
        if not conf_list:
            return

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title} ({len(conf_list)}개)*"
            }
        })

        for conf in conf_list:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_conference(conf)}
            })

        blocks.append({"type": "divider"})

    add_section("🔴 긴급 (30일내)", urgent)
    add_section("🟡 임박 (6개월내)", upcoming)
    add_section("🟢 여유 (6개월+)", later)

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST | Source: ccfddl"
            }
        ]
    })

    return {"blocks": blocks}


def format_slack_message(conferences):
    """Slack 메시지 포맷팅 - 학회별 그룹화, 기간별 분류"""
    current_year = datetime.now().year
    
    if not conferences:
        return {
            "text": f"📅 *Conference Deadline Alert*\n\n{current_year}-{current_year+1} 예정된 학회 데드라인이 없습니다."
        }
    
    # 기간별 분류
    urgent = [c for c in conferences if c['min_days_left'] <= 30]
    upcoming = [c for c in conferences if 30 < c['min_days_left'] <= 180]
    later = [c for c in conferences if c['min_days_left'] > 180]
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📅 Conference Deadline Alert",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔴 긴급 (30일내): {len(urgent)}  |  🟡 임박 (6개월내): {len(upcoming)}  |  🟢 여유 (6개월+): {len(later)}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{current_year}-{current_year+1} 총 {len(conferences)}개 학회*"
            }
        },
        {"type": "divider"}
    ]
    
    def get_urgency_emoji(days_left):
        if days_left <= 30:
            return "🔴"
        elif days_left <= 180:
            return "🟡"
        else:
            return "🟢"
    
    def format_conference(conf):
        """학회 정보 포맷팅"""
        emoji = get_urgency_emoji(conf['min_days_left'])
        
        # 학회명 (링크 포함)
        if conf.get('link'):
            conf_name = f"<{conf['link']}|{conf['name']} {conf['year']}>"
        else:
            conf_name = f"{conf['name']} {conf['year']}"
        
        rank_info = f" (CCF-{conf['ccf_rank']})" if conf.get('ccf_rank') else ""
        
        lines = [f"{emoji} *{conf_name}*{rank_info}"]
        lines.append(f"     📁 {conf['category']}")
        lines.append(f"     📍 {conf['place']}")
        lines.append(f"     🗓️ {conf['date']}")
        lines.append(f"     🕐 {conf.get('timezone', 'UTC-12')}")
        
        # Timeline 하위 항목
        for t in conf['timelines']:
            # KST 시간과 원본 시간 모두 표시
            orig_str = t['deadline'].strftime('%Y-%m-%d %H:%M')
            kst_str = t['deadline_kst'].strftime('%Y-%m-%d %H:%M')
            comment = f" ({t['comment']})" if t['comment'] else ""
            lines.append(f"     • {t['type']}: {kst_str} KST (D-{t['days_left']}) / {orig_str} {conf.get('timezone', '')}{comment}")
        
        return "\n".join(lines)
    
    def add_section(title, conf_list):
        if not conf_list:
            return
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title} ({len(conf_list)}개 학회)*"
            }
        })
        
        for conf in conf_list:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_conference(conf)}
            })
        
        blocks.append({"type": "divider"})
    
    add_section("🔴 긴급 (30일내)", urgent)
    add_section("🟡 임박 (6개월내)", upcoming)
    add_section("🟢 여유 (6개월+)", later)
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST | Source: ccfddl"
            }
        ]
    })
    
    return {"blocks": blocks}


def _post_to_slack(payload):
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code != 200:
            print(f"Slack error: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Slack notification: {e}")
        return False


def send_slack_notification(message):
    """Slack으로 메시지 전송 (메시지당 50블록 제한이 있어 초과 시 분할 전송)"""
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set")
        return False

    blocks = message.get('blocks')
    if blocks and len(blocks) > 50:
        ok = True
        for i in range(0, len(blocks), 50):
            ok = _post_to_slack({"blocks": blocks[i:i+50]}) and ok
        return ok

    return _post_to_slack(message)


def main():
    print("="*60)
    print("Conference Deadline Alert Bot v7")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 오늘 날짜 확인 (홀수일/짝수일)
    today = datetime.now(KST)
    is_odd_day = today.day % 2 == 1

    if is_odd_day:
        print(f"📅 오늘은 {today.day}일 (홀수일) - 분야별 전체 학회 알림")
    else:
        print(f"🎯 오늘은 {today.day}일 (짝수일) - 목표 학회 알림")

    # 학회 정보 수집
    conferences = collect_conferences()
    print(f"\nTotal collected: {len(conferences)} conference cycles")

    # 필터링
    upcoming = get_upcoming_conferences(conferences)
    current_year = datetime.now().year
    print(f"Upcoming ({current_year}-{current_year+1}): {len(upcoming)} conferences")

    # 홀수일/짝수일에 따라 다른 처리
    if is_odd_day:
        # 홀수일: 분야별 전체 학회
        display_conferences = upcoming
        print("\n--- 분야별 전체 학회 ---")
    else:
        # 짝수일: 목표 학회만
        display_conferences = filter_target_conferences(upcoming)
        print(f"\n--- 목표 학회 ({len(display_conferences)}개) ---")
        print(f"목표: {', '.join(TARGET_CONFERENCES)}")

    # 결과 출력
    for conf in display_conferences:
        print(f"\n[{conf['category']}] {conf['name']} {conf['year']} (D-{conf['min_days_left']})")
        print(f"  📍 {conf['place']} | 🗓️ {conf['date']} | 🕐 {conf['timezone']}")
        for t in conf['timelines']:
            kst_str = t['deadline_kst'].strftime('%Y-%m-%d %H:%M')
            print(f"  • {t['type']}: {kst_str} KST (D-{t['days_left']})")

    # Slack 메시지 생성 및 전송
    if is_odd_day:
        message = format_slack_message_by_category(display_conferences)
    else:
        message = format_slack_message_target(display_conferences)

    if send_slack_notification(message):
        print("\n✅ Slack notification sent successfully!")
    else:
        print("\n❌ Failed to send Slack notification")
        print(json.dumps(message, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()