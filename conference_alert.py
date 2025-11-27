#!/usr/bin/env python3
"""
Conference Deadline Alert Bot v6
학회별로 그룹화, 모든 deadline을 하위 항목으로 표시
"""

import requests
import json
import yaml
from datetime import datetime
import os

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# ccfddl에서 가져올 학회 목록 (카테고리/파일명)
CCFDDL_CONFERENCES = [
    # AI
    ("AI", "cvpr"),
    ("AI", "iccv"),
    ("AI", "eccv"),
    ("AI", "aaai"),
    ("AI", "ijcai"),
    ("AI", "icml"),
    ("AI", "nips"),  # NeurIPS
    ("AI", "iclr"),
    # Security
    ("SC", "sp"),      # IEEE S&P
    ("SC", "ccs"),
    ("SC", "uss"),     # USENIX Security
    ("SC", "ndss"),
    ("SC", "eurocrypt"),
    ("SC", "crypto"),
    ("SC", "asiacrypt"),
    ("SC", "esorics"),
    ("SC", "dsn"),
    # Network
    ("NW", "sigcomm"),
    ("NW", "infocom"),
    ("NW", "nsdi"),
    # Data/DB
    ("DB", "sigmod"),
    ("DB", "vldb"),
    ("DB", "icde"),
    ("DB", "kdd"),
    # System
    ("DS", "sigmetrics"),
]

CATEGORY_MAP = {
    "AI": "AI/Vision",
    "SC": "Security",
    "NW": "Network",
    "DB": "Data",
    "DS": "System",
    "SE": "Software",
}


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
                        timelines.append({
                            'type': 'Abstract Registration',
                            'deadline': abstract_date,
                            'comment': comment
                        })
                    
                    # Paper deadline
                    paper_str = t.get('deadline')
                    paper_date = parse_deadline(paper_str)
                    if paper_date:
                        timelines.append({
                            'type': 'Paper Submission',
                            'deadline': paper_date,
                            'comment': comment
                        })
                
                if timelines:
                    conferences.append({
                        'name': title,
                        'full_name': description,
                        'category': CATEGORY_MAP.get(sub, sub),
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
    today = datetime.now()
    current_year = today.year
    next_year = current_year + 1
    upcoming = []
    
    for conf in conferences:
        # 각 timeline의 days_left 계산
        future_timelines = []
        min_days_left = float('inf')
        
        for t in conf['timelines']:
            deadline = t['deadline']
            days_left = (deadline - today).days
            
            # 미래 deadline만 포함, 현재/다음 연도만
            if days_left >= 0 and deadline.year <= next_year:
                t['days_left'] = days_left
                future_timelines.append(t)
                min_days_left = min(min_days_left, days_left)
        
        if future_timelines:
            conf['timelines'] = sorted(future_timelines, key=lambda x: x['deadline'])
            conf['min_days_left'] = min_days_left
            upcoming.append(conf)
    
    # 가장 빠른 deadline 기준 정렬
    upcoming.sort(key=lambda x: x['min_days_left'])
    return upcoming


def format_slack_message(conferences):
    """Slack 메시지 포맷팅 - 학회별 그룹화, 기간별 분류"""
    current_year = datetime.now().year
    
    if not conferences:
        return {
            "text": f"📅 *Conference Deadline Alert*\n\n{current_year}-{current_year+1} 예정된 학회 데드라인이 없습니다."
        }
    
    # 기간별 분류
    urgent = [c for c in conferences if c['min_days_left'] <= 60]
    upcoming = [c for c in conferences if 60 < c['min_days_left'] <= 180]
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
                "text": f"*{current_year}-{current_year+1} 총 {len(conferences)}개 학회*"
            }
        },
        {"type": "divider"}
    ]
    
    def get_urgency_emoji(days_left):
        if days_left <= 3:
            return "🔴"
        elif days_left <= 7:
            return "🟠"
        elif days_left <= 14:
            return "🟡"
        elif days_left <= 60:
            return "🟢"
        else:
            return "⚪"
    
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
        
        # Timeline 하위 항목
        for t in conf['timelines']:
            date_str = t['deadline'].strftime('%Y-%m-%d %H:%M')
            comment = f" ({t['comment']})" if t['comment'] else ""
            lines.append(f"     • {t['type']}: {date_str} (D-{t['days_left']}){comment}")
        
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
    
    add_section("🚨 긴급 - 2달 이내", urgent)
    add_section("📌 다가오는 - 6달 이내", upcoming)
    add_section("📅 예정 - 6달 이후", later)
    
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


def send_slack_notification(message):
    """Slack으로 메시지 전송"""
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set")
        return False
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=message,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code != 200:
            print(f"Slack error: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Slack notification: {e}")
        return False


def main():
    print("="*60)
    print("Conference Deadline Alert Bot v6")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 학회 정보 수집
    conferences = collect_conferences()
    print(f"\nTotal collected: {len(conferences)} conference cycles")
    
    # 필터링
    upcoming = get_upcoming_conferences(conferences)
    current_year = datetime.now().year
    print(f"Upcoming ({current_year}-{current_year+1}): {len(upcoming)} conferences")
    
    # 결과 출력
    print("\n--- Upcoming Conferences ---")
    for conf in upcoming:
        print(f"\n[{conf['category']}] {conf['name']} {conf['year']} (D-{conf['min_days_left']})")
        print(f"  📍 {conf['place']} | 🗓️ {conf['date']}")
        for t in conf['timelines']:
            print(f"  • {t['type']}: {t['deadline'].strftime('%Y-%m-%d')} (D-{t['days_left']})")
    
    # Slack 메시지 생성 및 전송
    message = format_slack_message(upcoming)
    
    if send_slack_notification(message):
        print("\n✅ Slack notification sent successfully!")
    else:
        print("\n❌ Failed to send Slack notification")
        print(json.dumps(message, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()