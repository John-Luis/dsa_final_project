"""Dependency-free, accessible SVG reports generated entirely in Python."""
from collections import Counter
from datetime import date, timedelta
from html import escape
from math import ceil, cos, sin, pi
from markupsafe import Markup

STATUS_COLORS = {'Waiting':'#52866c','Called':'#d5ad62','For Assessment':'#719aa2',
                 'Skipped':'#b89077','Completed':'#165b49','Cancelled':'#bdc5b7'}


def chart_data(rows,start,end):
    first,last=date.fromisoformat(start),date.fromisoformat(end)
    days=(last-first).days+1
    span=max(1,ceil(days/14))
    buckets=[]
    cursor=first
    arrivals=Counter(r['day'] for r in rows)
    completed=Counter(r['day'] for r in rows if r['status']=='Completed')
    while cursor<=last:
        stop=cursor+timedelta(days=min(span-1,(last-cursor).days))
        # Count recorded days rather than iterating over potentially large empty date ranges.
        left,right=cursor.isoformat(),stop.isoformat()
        buckets.append(dict(label=cursor.strftime('%b %d'),start=left,end=right,
            received=sum(v for d,v in arrivals.items() if left<=d<=right),
            completed=sum(v for d,v in completed.items() if left<=d<=right)))
        if stop==last: break
        cursor=stop+timedelta(days=1)
    return dict(trend=buckets,span=span,statuses=Counter(r['status'] for r in rows))


def line_svg(buckets):
    max_value=max(1,max((b['received'] for b in buckets),default=0))
    step=max(1,ceil(max_value/4)); ceiling=step*4
    x=lambda i: 60+i*680/max(1,len(buckets)-1)
    y=lambda v: 200-v*160/ceiling
    parts=['<svg viewBox="0 0 800 265" role="img" aria-labelledby="trend-title trend-desc"><title id="trend-title">Request and completion trend</title><desc id="trend-desc">Requests received and currently completed, grouped by registration date. The data table follows this chart.</desc>']
    for n in range(5):
        value=n*step
        parts.append(f'<path d="M60 {y(value):.1f}H755" stroke="#e1e7dc"/><text x="44" y="{y(value)+4:.1f}" text-anchor="end" fill="#708075" font-size="11">{value}</text>')
    for field,color in [('received','#165b49'),('completed','#c19a4c')]:
        points=' '.join(f'{x(i):.1f},{y(b[field]):.1f}' for i,b in enumerate(buckets))
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}"/>')
        for i,b in enumerate(buckets):
            title=escape(f"{b['start']} to {b['end']}: {b[field]} {field}")
            parts.append(f'<circle cx="{x(i):.1f}" cy="{y(b[field]):.1f}" r="4" fill="{color}"><title>{title}</title></circle>')
    for i,b in enumerate(buckets):
        if i%max(1,ceil(len(buckets)/7))==0 or i==len(buckets)-1:
            parts.append(f'<text x="{x(i):.1f}" y="228" text-anchor="middle" fill="#708075" font-size="10">{escape(b["label"])}</text>')
    parts.append('</svg>')
    return Markup(''.join(parts))


def pie_svg(statuses):
    total=sum(statuses.values())
    parts=['<svg viewBox="0 0 260 240" role="img" aria-labelledby="pie-title"><title id="pie-title">Transaction status distribution</title>']
    if not total:
        parts.append('<circle cx="130" cy="112" r="88" fill="#e9eee3"/><text x="130" y="117" text-anchor="middle" fill="#708075" font-size="15">No data</text>')
    else:
        angle=-pi/2
        for status,color in STATUS_COLORS.items():
            value=statuses.get(status,0)
            if not value: continue
            end=angle+2*pi*value/total
            title=escape(f'{status}: {value} ({100*value/total:.1f}%)')
            if value==total:
                parts.append(f'<circle cx="130" cy="112" r="88" fill="{color}"><title>{title}</title></circle>')
            else:
                start_x,start_y=130+88*cos(angle),112+88*sin(angle)
                end_x,end_y=130+88*cos(end),112+88*sin(end)
                parts.append(f'<path d="M130 112 L{start_x:.4f} {start_y:.4f} A88 88 0 {int(value/total>0.5)} 1 {end_x:.4f} {end_y:.4f} Z" fill="{color}" stroke="#fff" stroke-width="2"><title>{title}</title></path>')
            angle=end
    parts.append('</svg>')
    return Markup(''.join(parts))
