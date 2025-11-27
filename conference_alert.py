#!/usr/bin/env python3
"""
Conference Deadline Alert Bot
탑티어 학회 데드라인을 크롤링하여 Slack으로 알림
"""

import requests
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import os

# Slack Webhook URL (환경변수로 설정)
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# 트래킹할 학회 목록
CONFERENCES = {
    "AI/Vision": [
        {"name": "CVPR", "wikicfp": "CVPR"},
        {"name": "ECCV", "wikicfp": "ECCV"},
        {"name": "ICCV", "wikicfp": "ICCV"},
        {"name": "AAAI", "wikicfp": "AAAI"},
        {"name": "ICML", "wikicfp": "ICML"},
        {"name": "ICLR", "wikicfp": "ICLR"},
        {"name": "NeurIPS", "wikicfp": "NeurIPS"},
    ],
    "Security": [
        {"name": "IEEE S&P", "wikicfp": "IEEE Symposium on Security and Privacy"},
        {"name": "CCS", "wikicfp": "CCS"},
        {"name": "USENIX Security", "wikicfp": "USENIX Security"},
        {"name": "NDSS", "wikicfp": "NDSS"},
        {"name": "Eurocrypt", "wikicfp": "Eurocrypt"},
        {"name": "ESORICS", "wikicfp": "ESORICS"},
        {"name": "DSN", "wikicfp": "DSN"},
        {"name": "Black Hat", "wikicfp": "Black Hat"},
    ],
    "Network": [
        {"name": "SIGMETRICS", "wikicfp": "SIGMETRICS"},
        {"name": "INFOCOM", "wikicfp": "INFOCOM"},
        {"name": "SIGCOMM", "wikicfp": "SIGCOMM"},
    ],
    "Data": [
        {"name": "ICDM", "wikicfp": "ICDM"},
        {"name": "IEEE BigData", "wikicfp": "IEEE BigData"},
    ],
}


def fetch_wikicfp_deadlines():
    """WikiCFP에서 학회 데드라인 정보 크롤링"""
    deadlines = []
    
    for category, confs in CONFERENCES.items():
        for conf in confs:
            try:
                # WikiCFP 검색
                search_url = f"http://www.wikicfp.com/cfp/servlet/tool.search?q={conf['wikicfp']}&year=2025"
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(search_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 테이블에서 정보 추출
                rows = soup.find_all('tr', {'bgcolor': ['#f6f6f6', '#e6e6e6']})
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        event_name = cols[0].get_text(strip=True)
                        # 해당 학회인지 확인
                        if conf['name'].lower() in event_name.lower():
                            deadline_text = cols[2].get_text(strip=True)
                            location = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                            
                            # 날짜 파싱 시도
                            deadline_date = parse_date(deadline_text)
                            
                            if deadline_date:
                                deadlines.append({
                                    "name": event_name,
                                    "category": category,
                                    "deadline": deadline_date,
                                    "deadline_str": deadline_text,
                                    "location": location,
                                })
                            break
            except Exception as e:
                print(f"Error fetching {conf['name']}: {e}")
                continue
    
    return deadlines


def parse_date(date_str):
    """다양한 날짜 형식 파싱"""
    formats = [
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def get_upcoming_deadlines(deadlines, days=30):
    """지정된 기간 내의 다가오는 데드라인 필터링"""
    today = datetime.now()
    upcoming = []
    
    for d in deadlines:
        if d['deadline']:
            days_left = (d['deadline'] - today).days
            if 0 <= days_left <= days:
                d['days_left'] = days_left
                upcoming.append(d)
    
    # 날짜순 정렬
    upcoming.sort(key=lambda x: x['deadline'])
    return upcoming


def format_slack_message(deadlines):
    """Slack 메시지 포맷팅"""
    if not deadlines:
        return {
            "text": "📅 *Conference Deadline Alert*\n\n향후 30일 내 마감되는 학회가 없습니다."
        }
    
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
                "text": f"*향후 30일 내 마감 학회: {len(deadlines)}개*"
            }
        },
        {"type": "divider"}
    ]
    
    for d in deadlines:
        days_left = d['days_left']
        
        # 긴급도에 따른 이모지
        if days_left <= 3:
            emoji = "🔴"
            urgency = "D-DAY!" if days_left == 0 else f"D-{days_left}"
        elif days_left <= 7:
            emoji = "🟠"
            urgency = f"D-{days_left}"
        else:
            emoji = "🟢"
            urgency = f"D-{days_left}"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{d['name']}*\n"
                        f"📁 {d['category']} | ⏰ {urgency}\n"
                        f"📆 {d['deadline'].strftime('%Y-%m-%d')} | 📍 {d.get('location', 'TBA')}"
            }
        })
    
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST"
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
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Slack notification: {e}")
        return False


def main():
    print("Fetching conference deadlines...")
    
    # 데드라인 수집
    deadlines = fetch_wikicfp_deadlines()
    print(f"Found {len(deadlines)} conferences")
    
    # 30일 내 마감 필터링
    upcoming = get_upcoming_deadlines(deadlines, days=30)
    print(f"Upcoming deadlines: {len(upcoming)}")
    
    # Slack 메시지 생성 및 전송
    message = format_slack_message(upcoming)
    
    if send_slack_notification(message):
        print("Slack notification sent successfully!")
    else:
        print("Failed to send Slack notification")
        # 디버그용 출력
        print(json.dumps(message, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()