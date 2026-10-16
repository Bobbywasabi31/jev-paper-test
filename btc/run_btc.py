"""Run one on-demand BTC paper evaluation. No trading/account API access."""
import os
import subprocess
import sys
import time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent


def healthy():
    try:
        r=requests.get('http://127.0.0.1:8013/health',timeout=3)
        r.raise_for_status()
        data=r.json()
        return data.get('status')=='ok' and data.get('model')=='MiniCPM5-2B-Jev'
    except requests.RequestException:
        return False


def ensure_server():
    if healthy():
        return
    # Do not launch over an unrelated listener.
    import socket
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',8013))==0:
            raise RuntimeError('Port 8013 is occupied but MiniCPM is not ready; retry after it loads.')
    with (ROOT/'server.log').open('a',encoding='utf-8') as log:
        subprocess.Popen([sys.executable,'-u',r'C:\Jev\serve.py','--host','127.0.0.1','--port','8013'],
                         cwd=r'C:\Jev',stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(60):
        if healthy():
            return
        time.sleep(5)
    raise RuntimeError('Model did not become ready; see server.log')


def run():
    print('Checking the Bitcoin model...',flush=True)
    ensure_server()
    failures=[]
    env=dict(os.environ,PYTHONUTF8='1')
    jobs=[('Kalshi BTC', [sys.executable,str(ROOT/'kalshi_btc.py')])]
    for cohort in ['baseline','enriched']:
        for command in ['settle','predict','report']:
            jobs.append((f'Bitcoin ETF / {cohort} / {command}',[sys.executable,str(ROOT/'etf/jev_market_test.py'),command,'--cohort',cohort,'--backend','minicpm']))
    print('Updating predictions and checking results. Please wait...',flush=True)
    with (ROOT/'technical_log.txt').open('w',encoding='utf-8') as log:
        for label,command in jobs:
            heading='\n===== '+label+' =====\n'
            log.write(heading);log.flush()
            proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            for line in proc.stdout:
                log.write(line);log.flush()
            if proc.wait():
                failures.append(label)
        ending='\nPAPER ONLY. No real trades. '+('FAILED: '+', '.join(failures) if failures else 'All stages completed.')+'\n'
        log.write(ending)
    from simple_report import build_summary
    summary=build_summary(failures)
    (ROOT/'latest_report.txt').write_text(summary,encoding='utf-8')
    print('\n'+summary,flush=True)
    return bool(failures)


if __name__=='__main__':
    import msvcrt
    with (ROOT/'.run.lock').open('a+b') as lock:
        if lock.tell()==0:
            lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            raise SystemExit('A BTC suite run is already active.')
        try:
            sys.exit(run())
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
