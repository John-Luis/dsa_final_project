"""Aggregate request records for operational reporting (not an official DOLE form)."""
from collections import Counter
from datetime import datetime


def summarize(rows):
    volumes = Counter(r['program'] for r in rows)
    hours = Counter(datetime.fromisoformat(r['created_at']).hour for r in rows)
    waits = [(datetime.fromisoformat(r['called_at'])-datetime.fromisoformat(r['queued_at'])).total_seconds()/60
             for r in rows if r['called_at']]
    durations = [(datetime.fromisoformat(r['completed_at'])-datetime.fromisoformat(r['called_at'])).total_seconds()/60
                 for r in rows if r['completed_at'] and r['called_at']]
    return dict(total=len(rows),completed=sum(r['status']=='Completed' for r in rows),
        average_wait=round(sum(waits)/len(waits),1) if waits else None,
        average_service=round(sum(durations)/len(durations),1) if durations else None,
        measured_waits=len(waits),volumes=volumes,hours=hours,
        peak=max(hours,key=lambda h:(hours[h],-h)) if hours else None)


def csv_safe(value):
    # Prevent spreadsheet formula execution in user-entered text, including leading whitespace.
    text = str(value) if value is not None else ''
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text
