#!/usr/bin/env python3
"""
Conference Deadline Alert Bot v4
GitHub raw에서 직접 YAML 파일을 가져옴
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

# 카테고리 매핑
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
            data = yaml.safe_load(response.text)
            return data
    except Exception as e:
        print(f"[ccfddl] Error fetching {sub}/{name}: {e}")
    
    return None


def fetch_sec_deadlines():
    """sec-deadlines GitHub에서 학회 데이터 가져오기"""
    url = "https://raw.githubusercontent.com/sec-deadlines/sec-deadlines.github.io/master/_data/conferences.yml"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = yaml.safe_load(response.text)
            return data
    except Exception as e:
        print(f"[sec-deadlines] Error: {e}")
    
    return []


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


def collect_ccfddl_deadlines():
    """ccfddl에서 모든 타겟 학회 데드라인 수집"""
    deadlines = []
    
    for sub, name in CCFDDL_CONFERENCES:
        data = fetch_ccfddl_conference(sub, name)
        if not data:
            continue
        
        for conf in data:
            title = conf.get('title', '')
            description = conf.get('description', '')
            rank = conf.get('rank', {}).get('ccf', '')
            
            confs = conf.get('confs', [])
            for cycle in confs:
                year = cycle.get('year', '')
                link = cycle.get('link', '')
                place = cycle.get('place', 'TBA')
                
                timeline = cycle.get('timeline', [])
                for t in timeline:
                    # Abstract deadline 추가
                    abstract_str = t.get('abstract_deadline')
                    abstract_date = parse_deadline(abstract_str)
                    if abstract_date:
                        deadlines.append({
                            'name': title,
                            'full_name': description,
                            'category': CATEGORY_MAP.get(sub, sub),
                            'ccf_rank': rank,
                            'year': year,
                            'deadline': abstract_date,
                            'deadline_str': abstract_str,
                            'place': place,
                            'link': link,
                            'comment': f"Abstract - {t.get('comment', '')}".strip(' -'),
                            'deadline_type': 'abstract',
                            'source': 'ccfddl'
                        })
                    
                    # Paper deadline
                    deadline_str = t.get('deadline')
                    deadline_date = parse_deadline(deadline_str)
                    if deadline_date:
                        deadlines.append({
                            'name': title,
                            'full_name': description,
                            'category': CATEGORY_MAP.get(sub, sub),
                            'ccf_rank': rank,
                            'year': year,
                            'deadline': deadline_date,
                            'deadline_str': deadline_str,
                            'place': place,
                            'link': link,
                            'comment': t.get('comment', ''),
                            'deadline_type': 'paper',
                            'source': 'ccfddl'
                        })
        
        print(f"[ccfddl] Fetched {sub}/{name}")
    
    return deadlines


def collect_sec_deadlines():
    """sec-deadlines에서 데드라인 수집"""
    deadlines = []
    data = fetch_sec_deadlines()
    
    if not data:
        return deadlines
    
    # 타겟 학회 필터
    target_names = ['s&p', 'sp', 'oakland', 'ccs', 'usenix security', 'ndss', 
                    'eurocrypt', 'crypto', 'esorics', 'dsn']
    
    for conf in data:
        name = conf.get('name', '').lower()
        
        # 타겟 학회인지 확인
        is_target = any(t in name for t in target_names)
        if not is_target:
            continue
        
        deadline_list = conf.get('deadline', [])
        if isinstance(deadline_list, str):
            deadline_list = [deadline_list]
        
        for dl in deadline_list:
            # rolling deadline 처리
            year = conf.get('year', datetime.now().year)
            resolved = str(dl).replace('%y', str(year)).replace('%Y', str(int(year) - 1))
            
            deadline_date = parse_deadline(resolved)
            if deadline_date:
                deadlines.append({
                    'name': conf.get('name', ''),
                    'full_name': conf.get('description', ''),
                    'category': 'Security',
                    'ccf_rank': '',
                    'year': year,
                    'deadline': deadline_date,
                    'deadline_str': resolved,
                    'place': conf.get('place', 'TBA'),
                    'link': conf.get('link', ''),
                    'comment': '',
                    'deadline_type': 'paper',
                    'source': 'sec-deadlines'
                })
    
    print(f"[sec-deadlines] Fetched {len(deadlines)} deadlines")
    return deadlines


def get_upcoming_deadlines(deadlines):
    """현재 연도 + 다음 연도까지의 미래 데드라인 필터링"""
    today = datetime.now()
    current_year = today.year
    next_year = current_year + 1
    upcoming = []
    seen = set()
    
    for d in deadlines:
        deadline = d.get('deadline')
        if not deadline:
            continue
        
        deadline_year = deadline.year
        days_left = (deadline - today).days
        
        # 과거가 아니고, 현재 연도 또는 다음 연도인 것만
        if days_left >= 0 and deadline_year <= next_year:
            # 중복 제거 (학회명 + 연도 + deadline)
            key = f"{d['name'].lower()}_{deadline.strftime('%Y-%m-%d')}"
            if key in seen:
                continue
            seen.add(key)
            
            d['days_left'] = days_left
            upcoming.append(d)
    
    upcoming.sort(key=lambda x: x['deadline'])
    return upcoming


def format_slack_message(deadlines):
    """Slack 메시지 포맷팅 - 기간별 분류"""
    current_year = datetime.now().year
    
    if not deadlines:
        return {
            "text": f"📅 *Conference Deadline Alert*\n\n{current_year}-{current_year+1} 예정된 학회 데드라인이 없습니다."
        }
    
    # 기간별 분류
    urgent = []      # 2달 이내 (60일)
    upcoming = []    # 6달 이내 (180일)
    later = []       # 12달 이상
    
    for d in deadlines:
        days_left = d['days_left']
        if days_left <= 60:
            urgent.append(d)
        elif days_left <= 180:
            upcoming.append(d)
        else:
            later.append(d)
    
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
                "text": f"*{current_year}-{current_year+1} 총 {len(deadlines)}개 데드라인*"
            }
        },
        {"type": "divider"}
    ]
    
    def format_deadline_entry(d):
        days_left = d['days_left']
        
        if days_left <= 3:
            emoji = "🔴"
        elif days_left <= 7:
            emoji = "🟠"
        elif days_left <= 14:
            emoji = "🟡"
        elif days_left <= 60:
            emoji = "🟢"
        else:
            emoji = "⚪"
        
        conf_name = d['name']
        if d.get('link'):
            conf_name = f"<{d['link']}|{d['name']}>"
        
        rank_info = f" (CCF-{d['ccf_rank']})" if d.get('ccf_rank') else ""
        
        # deadline type 표시
        if d.get('deadline_type') == 'abstract':
            type_label = "Abstract Registration"
        else:
            type_label = "Paper Submission"
        
        comment = f" | {d['comment']}" if d.get('comment') else ""
        
        return f"{emoji} *{conf_name}*{rank_info}\n" \
               f"     📌 {type_label}\n" \
               f"     📆 {d['deadline'].strftime('%Y-%m-%d %H:%M')} (D-{days_left}){comment}"
    
    # 🚨 긴급 (2달 이내)
    if urgent:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🚨 긴급 - 2달 이내 ({len(urgent)}개)*"
            }
        })
        for d in urgent:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_deadline_entry(d)}
            })
        blocks.append({"type": "divider"})
    
    # 📌 다가오는 (6달 이내)
    if upcoming:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📌 다가오는 - 6달 이내 ({len(upcoming)}개)*"
            }
        })
        for d in upcoming:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_deadline_entry(d)}
            })
        blocks.append({"type": "divider"})
    
    # 📅 예정 (12달 이상)
    if later:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📅 예정 - 6달 이후 ({len(later)}개)*"
            }
        })
        for d in later:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": format_deadline_entry(d)}
            })
        blocks.append({"type": "divider"})
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST | Source: ccfddl, sec-deadlines"
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
    print("Conference Deadline Alert Bot v4")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 데드라인 수집
    all_deadlines = []
    all_deadlines.extend(collect_ccfddl_deadlines())
    all_deadlines.extend(collect_sec_deadlines())
    
    print(f"\nTotal collected: {len(all_deadlines)}")
    
    # 필터링
    upcoming = get_upcoming_deadlines(all_deadlines)
    current_year = datetime.now().year
    print(f"Upcoming deadlines ({current_year}-{current_year+1}): {len(upcoming)}")
    
    # 결과 출력
    print("\n--- Upcoming Deadlines ---")
    for d in upcoming:
        print(f"  [{d['category']}] {d['name']}: {d['deadline'].strftime('%Y-%m-%d')} (D-{d['days_left']})")
    
    # Slack 메시지 생성 및 전송
    message = format_slack_message(upcoming)
    
    if send_slack_notification(message):
        print("\n✅ Slack notification sent successfully!")
    else:
        print("\n❌ Failed to send Slack notification")
        print(json.dumps(message, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()