#!/usr/bin/env python3
"""scripts/align_mix_windows.py - Cross-Platform Window Alignment for Mix Manager"""
import sys, os, time, subprocess, argparse, json, tempfile

def main():
    args = get_args()
    aligned = align_windows(timeout=args.timeout, mgr_pid=args.mgr_pid, parent_pid=args.parent_pid,
                            expect_audacious=args.expect_audacious, expect_strawberry=args.expect_strawberry,
                            expect_player=args.expect_player, expect_cover=args.expect_cover)
    if not aligned and shutil_which('wmctrl'): aligned = align_x11(mgr_pid=args.mgr_pid)
    sys.exit(0 if aligned else 1)

def get_args():
    parser = argparse.ArgumentParser(description="MP Mix Archive Manager Window Aligner")
    for opt in ['--mgr-pid', '--parent-pid']: parser.add_argument(opt, type=int, default=0)
    for opt in ['--expect-audacious', '--expect-strawberry', '--expect-player', '--expect-cover']: parser.add_argument(opt, action='store_true')
    parser.add_argument('--timeout', type=float, default=8.0)
    return parser.parse_known_args()[0]

def shutil_which(cmd):
    from shutil import which; return which(cmd) is not None

def get_ancestor_pids(*pids):
    ancestors = []
    for start_pid in pids:
        curr = start_pid
        while curr and curr > 1:
            ancestors.append(curr)
            try:
                with open(f"/proc/{curr}/stat", "r") as f: ppid = int(f.read().split()[3])
                if ppid == curr or ppid <= 1:
                    if ppid > 1: ancestors.append(ppid)
                    break
                curr = ppid
            except Exception: break
    return list(set(ancestors))

def is_running(names):
    my_pid = os.getpid()
    for name in names:
        try:
            out = subprocess.check_output(['pgrep', '-i', name], stderr=subprocess.DEVNULL).decode()
            if any(int(p) != my_pid for p in out.split() if p.isdigit()): return True
        except Exception: pass
    return False

def get_display_priorities():
    try:
        raw = subprocess.check_output(['kscreen-doctor', '-j'], stderr=subprocess.DEVNULL)
        outputs = []
        for o in json.loads(raw).get('outputs', []):
            if o.get('connected', True) and o.get('enabled', True):
                name = o.get('name', '')
                if not name.lower().startswith('unknown'):
                    pos = o.get('pos', {})
                    outputs.append({'name': name, 'priority': o.get('priority', 999), 'x': pos.get('x', 0), 'y': pos.get('y', 0)})
        if outputs:
            outputs.sort(key=lambda x: (x['priority'], x['x'], x['y']))
            return outputs[0]['name'], (outputs[1]['name'] if len(outputs) > 1 else None)
    except Exception: pass
    return '', None

def can_align_kwin():
    try:
        import dbus
        bus = dbus.SessionBus()
        bus.get_object('org.kde.KWin', '/Scripting')
        return True
    except Exception: return False

def align_windows(timeout=8.0, mgr_pid=0, parent_pid=0, expect_audacious=False,
                  expect_strawberry=False, expect_player=False, expect_cover=False):
    if not can_align_kwin(): return False
    import dbus
    run_token = f"T{int(time.time() * 1000)}_{os.getpid()}"
    mgr_ancestors = get_ancestor_pids(mgr_pid, parent_pid)
    prim_name, sec_name = get_display_priorities()
    start_time, aligned_any = time.time(), False

    while time.time() - start_time < timeout:
        expect_straw = expect_strawberry or expect_audacious or expect_player or is_running(['audacious', 'strawberry'])
        expect_cov = expect_cover or is_running(['gwenview', 'loupe', 'eog', 'feh'])
        try:
            kwin_obj = dbus.SessionBus().get_object('org.kde.KWin', '/Scripting')
            scripting = dbus.Interface(kwin_obj, 'org.kde.kwin.Scripting')
            code = js_code(prim_name or '', sec_name or '', mgr_ancestors, mgr_pid, parent_pid, expect_straw, expect_cov, run_token)
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
                f.write(code); tmp_js = f.name
            pname = f"mix_align_{int(time.time() * 1000)}"
            try:
                num = scripting.loadScript(tmp_js, pname, signature='ss')
                if num >= 0:
                    dbus.SessionBus().get_object('org.kde.KWin', f'/Scripting/Script{num}').run()
                    aligned_any = True
                try: scripting.unloadScript(pname)
                except Exception: pass
            finally:
                if os.path.exists(tmp_js): os.remove(tmp_js)

            try:
                res = subprocess.run(['journalctl', '--user', '-n', '20', '--no-pager'], capture_output=True, text=True)
                for line in reversed(res.stdout.splitlines()):
                    if f"MIX_ALIGN_RUN:{run_token}" in line and "DONE:1" in line: return True
            except Exception: pass
        except Exception: pass
        time.sleep(0.25)
    return aligned_any

def js_code(prim_name, sec_name, mgr_ancestors, mgr_pid, parent_pid, expect_straw, expect_cover, run_token):
    return f'''
(function() {{
  var runToken="{run_token}", mgrAncestorPids={json.dumps(mgr_ancestors)}, mgrPid={mgr_pid}, parentPid={parent_pid};
  var expectStraw={json.dumps(expect_straw)}, expectCover={json.dumps(expect_cover)};
  var primScreenName="{prim_name}", secScreenName="{sec_name or ''}";
  var screens=workspace.screens||[], numScreens=screens.length, primScreen=null, secScreen=null;
  for(var s=0;s<screens.length;s++) {{
    if(screens[s].name===primScreenName && !primScreen) primScreen=screens[s];
    if(screens[s].name===secScreenName && !secScreen) secScreen=screens[s];
  }}
  if(!primScreen&&screens.length>0) primScreen=screens[0];
  if(!secScreen&&screens.length>1) {{
    for(var s=0;s<screens.length;s++) {{ if(screens[s]!==primScreen) {{ secScreen=screens[s]; break; }} }}
  }}
  var wins=workspace.windowList(), mgrWin=null, strawWin=null, coverWin=null, tlWin=null;
  for(var i=0;i<wins.length;i++) {{
    var w=wins[i], cap=w.caption||'', capLower=cap.toLowerCase(), rClass=(w.resourceClass||'').toLowerCase();
    if(!mgrWin && ((mgrAncestorPids&&mgrAncestorPids.indexOf(w.pid)!==-1)||(mgrPid>0&&w.pid===mgrPid)||(parentPid>0&&w.pid===parentPid)||cap.indexOf('Mix Archive Manager')!==-1||capLower.indexOf('mix manager')!==-1||(rClass.indexOf('konsole')!==-1&&(capLower.indexOf('mix')!==-1||capLower.indexOf('bash_scripts')!==-1)))) {{ mgrWin=w; continue; }}
    if(!strawWin && (rClass.indexOf('audacious')!==-1||capLower.indexOf('audacious')!==-1||rClass.indexOf('strawberry')!==-1||capLower.indexOf('strawberry')!==-1)) {{ strawWin=w; continue; }}
    if(!coverWin && (rClass.indexOf('gwenview')!==-1||capLower.indexOf('gwenview')!==-1||rClass.indexOf('loupe')!==-1||rClass.indexOf('eog')!==-1||capLower.indexOf('cover')!==-1)) {{ coverWin=w; continue; }}
    if(!tlWin && (cap.indexOf('Tracklist')!==-1&&rClass.indexOf('konsole')!==-1)) {{ tlWin=w; continue; }}
  }}
  var isDone=false;
  if(numScreens>1&&primScreen&&secScreen) {{
    var pArea=workspace.clientArea(0,primScreen,workspace.currentDesktop);
    var sArea=workspace.clientArea(0,secScreen,workspace.currentDesktop);
    if(mgrWin) {{ workspace.sendClientToScreen(mgrWin,primScreen); workspace.raiseWindow(mgrWin); }}
    if(tlWin) {{ tlWin.minimized=true; }}
    if(expectStraw&&!strawWin) {{ console.warn("MIX_ALIGN_RUN:"+runToken+" DONE:0 WAIT:player"); return; }}
    if(expectCover&&!coverWin) {{ console.warn("MIX_ALIGN_RUN:"+runToken+" DONE:0 WAIT:cover"); return; }}
    if(coverWin&&strawWin) {{
      var gap=16, coverW=Math.min(sArea.height-40,Math.floor(sArea.width*0.42)), coverH=coverW;
      var coverX=sArea.x+15, coverY=sArea.y+Math.floor((sArea.height-coverH)/2);
      coverWin.fullScreen=false; if(coverWin.setMaximize) coverWin.setMaximize(false,false);
      workspace.sendClientToScreen(coverWin,secScreen); coverWin.frameGeometry={{x:coverX,y:coverY,width:coverW,height:coverH}};
      coverWin.keepAbove=true; workspace.raiseWindow(coverWin);
      var strawX=coverX+coverW+gap, strawW=(sArea.x+sArea.width)-strawX-15, strawY=sArea.y+15, strawH=sArea.height-30;
      strawWin.fullScreen=false; if(strawWin.setMaximize) strawWin.setMaximize(false,false);
      workspace.sendClientToScreen(strawWin,secScreen); strawWin.frameGeometry={{x:strawX,y:strawY,width:strawW,height:strawH}};
      workspace.raiseWindow(strawWin); isDone=true;
    }} else if(strawWin&&!expectCover) {{
      strawWin.fullScreen=false; if(strawWin.setMaximize) strawWin.setMaximize(false,false);
      workspace.sendClientToScreen(strawWin,secScreen); strawWin.frameGeometry={{x:sArea.x+20,y:sArea.y+20,width:sArea.width-40,height:sArea.height-40}};
      workspace.raiseWindow(strawWin); isDone=true;
    }} else if(coverWin&&!expectStraw) {{
      var targetH=Math.min(sArea.height-40,Math.max(500,Math.floor(sArea.height*0.85))), coverW=Math.min(targetH,Math.floor(sArea.width*0.45));
      coverWin.fullScreen=false; if(coverWin.setMaximize) coverWin.setMaximize(false,false);
      workspace.sendClientToScreen(coverWin,secScreen); coverWin.frameGeometry={{x:sArea.x+Math.floor((sArea.width-coverW)/2),y:sArea.y+Math.floor((sArea.height-targetH)/2),width:coverW,height:targetH}};
      coverWin.keepAbove=true; workspace.raiseWindow(coverWin); isDone=true;
    }} else isDone=true;
  }} else {{
    var refWin=tlWin||coverWin||workspace.activeWindow;
    var screen=(refWin&&refWin.output)?refWin.output:(primScreen||workspace.activeScreen);
    var sArea=workspace.clientArea(0,screen,workspace.currentDesktop);
    var sX=Math.floor(sArea.x), sY=Math.floor(sArea.y), sW=Math.floor(sArea.width), sH=Math.floor(sArea.height);
    if(mgrWin) {{ workspace.sendClientToScreen(mgrWin,screen); workspace.raiseWindow(mgrWin); }}
    var targetH=Math.min(760,Math.max(500,Math.floor(sH*0.65)));
    var coverW=coverWin?Math.min(targetH,Math.floor(sW*0.38)):0, tlW=tlWin?Math.min(960,Math.max(680,Math.floor(sW*0.44))):0;
    if(coverWin) {{ coverWin.fullScreen=false; if(coverWin.setMaximize) coverWin.setMaximize(false,false); workspace.sendClientToScreen(coverWin,screen); coverWin.keepAbove=true; coverWin.frameGeometry={{x:sX+10,y:sY+10,width:Math.floor((sW-40)/2),height:targetH}}; workspace.raiseWindow(coverWin); }}
    if(tlWin) {{ tlWin.fullScreen=false; if(tlWin.setMaximize) tlWin.setMaximize(false,false); workspace.sendClientToScreen(tlWin,screen); tlWin.keepAbove=true; tlWin.noBorder=true; tlWin.frameGeometry={{x:sX+10,y:sY+10,width:Math.floor((sW-40)/2),height:targetH}}; workspace.raiseWindow(tlWin); }}
    isDone=true;
  }}
  console.warn("MIX_ALIGN_RUN:"+runToken+" DONE:"+(isDone?1:0));
}})();'''

def align_x11(mgr_pid=0):
    try:
        wm_out = subprocess.check_output(['wmctrl', '-l', '-p', '-G'], text=True, errors='ignore')
        mgr_win = None
        for line in wm_out.splitlines():
            parts = line.split(maxsplit=8)
            if len(parts) >= 9:
                wid, pid_str, title = parts[0], parts[2], parts[8].lower()
                if (mgr_pid > 0 and pid_str.isdigit() and int(pid_str) == mgr_pid) or 'mix archive manager' in title:
                    mgr_win = wid; break
        if mgr_win:
            subprocess.run(['wmctrl', '-i', '-a', mgr_win], check=False)
            return True
    except Exception: pass
    return False

if __name__ == '__main__':
    main()