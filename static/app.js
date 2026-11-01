const $ = id => document.getElementById(id);
const saved = JSON.parse(localStorage.getItem('ranklocal-project') || 'null');
const project = saved && Array.isArray(saved.clips) ? saved : {title:'Top Goals With Most Aura',accent:'',audio:true,clips:[]};
let restoredOldImports=0;
if(!project.fullLengthImportV2) {
  for(const clip of project.clips) {
    if(Number(clip.start)===0 && Math.abs(Number(clip.end)-8)<.05 && Number(clip.duration)>8.05) {
      clip.end=clip.duration;
      restoredOldImports++;
    }
  }
  project.fullLengthImportV2=true;
}
for(const clip of project.clips) if(typeof clip.muted!=='boolean') clip.muted=project.audio===false;
if(!project.rankVersion) {
  project.clips.forEach((clip,index)=>{clip.rank=project.clips.length-index;});
  project.rankVersion=1;
  project.ranksLocked=false;
}
Object.assign(project, {titleFont:project.titleFont || 'Arial', titleColor:project.titleColor || '#ffffff', accentColor:project.accentColor || '#45b6ff', titleSize:project.titleSize || 77});
let selected = 0;
let playing = false;
let exporting = false;
let openTrimId = null;
const main = $('mainVideo');
const bg = $('bgVideo');
const musicAudio = $('musicAudio');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function save() { localStorage.setItem('ranklocal-project', JSON.stringify(project)); }
function totalTime() { return project.clips.reduce((sum, c) => sum + Math.max(0, Number(c.end)-Number(c.start)), 0); }
function formatTime(seconds) { const s=Math.max(0,Math.floor(seconds)); return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`; }
function currentTime() { return project.clips.slice(0,selected).reduce((sum,c)=>sum+Number(c.end)-Number(c.start),0) + (project.clips[selected] ? Math.max(0, main.currentTime-Number(project.clips[selected].start)) : 0); }
function syncTitleStyle() {
  const family = {Arial:'Arial, sans-serif',Impact:'Impact, sans-serif',Georgia:'Georgia, serif',Trebuchet:'"Trebuchet MS", sans-serif',Verdana:'Verdana, sans-serif'}[project.titleFont] || 'Arial, sans-serif';
  const size = Math.max(60,Math.min(100,Number(project.titleSize)||77));
  const pixels = size * ($('preview').clientWidth / 1080);
  for(const id of ['previewTitle','previewAccent']) { $(id).style.fontFamily=family; $(id).style.fontSize=`${pixels}px`; }
  $('previewTitle').style.color=project.titleColor;
  $('previewAccent').style.color=project.accentColor;
  $('titleSizeValue').textContent=`${size} px`;
}
function syncText() {
  $('previewTitle').textContent = project.title || 'Top Moments';
  $('previewAccent').textContent = project.accent || '';
  syncTitleStyle();
  const approximateLines = Math.max(1, Math.ceil((project.title || 'Top Moments').length / 23));
  $('previewAccent').style.top = `${(168 + 88 * Math.min(approximateLines, 3)) / 1920 * 100}%`;
  const n=project.clips.length;
  const ranked=project.clips.map((c,i)=>({c,i})).sort((a,b)=>a.c.rank-b.c.rank);
  $('previewRanks').innerHTML = ranked.map(({c,i})=>`<div class="preview-rank ${i===selected?'current':''}"><b>${c.rank}.</b><span>${i<=selected?escapeHtml(c.label || `Moment ${c.rank}`):''}</span></div>`).join('');
  $('nowPlaying').textContent = n ? `#${project.clips[selected]?.rank} · ${project.clips[selected]?.label || project.clips[selected]?.name || 'Moment'}` : 'No clips yet';
  $('timeInfo').textContent = `${formatTime(currentTime())} / ${formatTime(totalTime())}`;
  $('emptyPreview').style.display = n ? 'none' : 'flex';
  $('playBtn').disabled = !n;
  $('exportBtn').disabled = !n || exporting;
  $('clipCount').textContent = `${n} / 8`;
  $('shuffleBtn').disabled=n<2||exporting;
  $('playOrder').textContent=n?`Playback: ${project.clips.map(c=>`#${c.rank}`).join('  →  ')}`:'';
}
function renderRows() {
  const n=project.clips.length;
  $('clipList').innerHTML = project.clips.map((c,i)=>`<div class="clip-row ${i===selected?'selected':''}" draggable="true" data-index="${i}">
    <div class="clip-top"><span class="rank-pill">#${c.rank}</span><span class="play-index">PLAY ${String(i+1).padStart(2,'0')}</span><span class="clip-name" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span><span class="duration">${formatTime(Number(c.end)-Number(c.start))}</span><button class="audio-toggle ${c.muted?'muted':''}" data-action="mute" title="${c.muted?'Turn on clip sound':'Mute this clip'}">${c.muted?'Muted':'Sound on'}</button><button class="row-btn" data-action="up" title="Move earlier">↑</button><button class="row-btn" data-action="down" title="Move later">↓</button><button class="row-btn" data-action="remove" title="Remove">×</button></div>
    <div class="clip-fields"><label>Rank label<input data-field="label" maxlength="46" value="${escapeHtml(c.label)}" placeholder="Moment ${n-i}"></label>
      <details class="manual-trim" ${openTrimId===c.id?'open':''}><summary>Trim manually · ${Number(c.start)===0 && Math.abs(Number(c.end)-Number(c.duration))<.1?'full clip':`${Number(c.start).toFixed(1)}–${Number(c.end).toFixed(1)}s`}</summary>
        <div class="trim-controls"><label>Start (s)<input data-field="start" type="number" min="0" max="${c.duration}" step="0.1" value="${c.start}"></label><label>End (s)<input data-field="end" type="number" min="0.1" max="${c.duration}" step="0.1" value="${c.end}"></label></div><p class="trim-note">Nothing cut automatically. Change these only if you want.</p>
      </details></div>
  </div>`).join('');
  syncText();
  save();
}
async function preparePreview(c, play) {
  $('uploadStatus').textContent = `Preparing preview for ${c.name}…`;
  try {
    const response = await fetch('/api/preview', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:c.id})});
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'Preview conversion failed');
    c.preview = data.url;
    save();
    $('uploadStatus').textContent = '';
    if(project.clips[selected]?.id === c.id) loadSelected(play);
  } catch(error) { $('uploadStatus').textContent = error.message; }
}
function loadSelected(play=false) {
  const c=project.clips[selected];
  if(!c) { main.removeAttribute('src'); bg.removeAttribute('src'); syncText(); return; }
  if(!c.preview && !/\.(mp4|webm)$/i.test(c.id)) { preparePreview(c,play); return; }
  main.src=bg.src=c.preview || `/media/${encodeURIComponent(c.id)}`;
  main.onerror=()=>{ if(!c.preview) preparePreview(c,play); else $('uploadStatus').textContent=`Preview unavailable for ${c.name}`; };
  main.onloadedmetadata=()=>{
    const start=Math.min(Number(c.start),main.duration || Number(c.start));
    const ready=()=>{ bg.currentTime=main.currentTime; if(play) startPlayback(); syncText(); };
    if(Math.abs(main.currentTime-start)>.05){main.onseeked=()=>{main.onseeked=null;ready();};main.currentTime=start;}
    else ready();
  };
  syncText();
}
function select(index, play=false, continuous=false) {
  selected=Math.max(0,Math.min(index,project.clips.length-1));
  main.pause(); bg.pause(); playing=false;
  if(!continuous) musicAudio.pause();
  $('playBtn').textContent='▶';
  renderRows(); loadSelected(play);
}
function startPlayback() {
  if(!project.clips.length) return;
  playing=true;
  main.muted=!!project.clips[selected].muted;
  main.play().catch(()=>{playing=false; $('playBtn').textContent='▶';});
  bg.play().catch(()=>{});
  if(project.music){
    musicAudio.volume=Number(project.music.volume);
    if(musicAudio.paused){
      if(Number.isFinite(musicAudio.duration) && musicAudio.duration>0) musicAudio.currentTime=currentTime()%musicAudio.duration;
      musicAudio.play().catch(()=>{$('audioStatus').textContent='Audio preview unavailable. Export can still use this file.';});
    }
  }
  $('playBtn').textContent='Ⅱ';
}
function stopPlayback() { playing=false; main.pause(); bg.pause(); musicAudio.pause(); $('playBtn').textContent='▶'; }
main.addEventListener('timeupdate',()=>{
  const c=project.clips[selected]; if(!c) return;
  if(Math.abs(bg.currentTime-main.currentTime)>.3) bg.currentTime=main.currentTime;
  $('timeInfo').textContent=`${formatTime(currentTime())} / ${formatTime(totalTime())}`;
  if(playing && main.currentTime>=Number(c.end)-.04) {
    if(selected<project.clips.length-1) select(selected+1,true,true); else {stopPlayback(); main.currentTime=Number(c.start);}
  }
});
$('playBtn').onclick=()=>playing?stopPlayback():startPlayback();
$('titleInput').value=project.title;
$('accentInput').value=project.accent;
for(const [field,id] of [['title','titleInput'],['accent','accentInput']]) $(id).addEventListener('input',e=>{project[field]=e.target.value; save(); syncText();});
for(const [field,id] of [['titleFont','fontInput'],['titleColor','titleColorInput'],['accentColor','accentColorInput'],['titleSize','titleSizeInput']]) {
  $(id).value=project[field];
  const update=e=>{project[field]=field==='titleSize'?Number(e.target.value):e.target.value;save();syncText();};
  $(id).addEventListener('input',update);
  $(id).addEventListener('change',update);
}
function syncMusic(){
  const music=project.music;
  $('musicControls').hidden=!music;
  $('musicName').textContent=music?.name || '';
  $('musicVolumeInput').value=music?Math.round(Number(music.volume)*100):30;
  $('musicVolumeValue').textContent=`${$('musicVolumeInput').value}%`;
  musicAudio.volume=music?Number(music.volume):.3;
  const source=music?`/audio/${encodeURIComponent(music.id)}`:'';
  if(musicAudio.getAttribute('src')!==source){musicAudio.pause();if(source)musicAudio.src=source;else musicAudio.removeAttribute('src');}
}
syncMusic();
$('audioFileInput').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;
  $('audioStatus').textContent=`Adding ${file.name}…`;
  try{
    const response=await fetch('/api/upload-audio',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name)},body:file});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Audio upload failed');
    const old=project.music;
    project.music={id:data.id,name:file.name,volume:old?.volume ?? .3};
    syncMusic();save();$('audioStatus').textContent=`Added ${file.name}`;
    if(old)fetch(`/api/audio/${encodeURIComponent(old.id)}`,{method:'DELETE'}).catch(()=>{});
  }catch(error){$('audioStatus').textContent=error.message;}
  e.target.value='';
});
$('musicVolumeInput').addEventListener('input',e=>{
  if(!project.music)return;
  project.music.volume=Number(e.target.value)/100;
  musicAudio.volume=project.music.volume;
  $('musicVolumeValue').textContent=`${e.target.value}%`;
  save();
});
$('removeMusicBtn').onclick=()=>{
  if(exporting||!project.music)return;
  const old=project.music;project.music=null;syncMusic();save();
  $('audioStatus').textContent='Audio removed.';
  fetch(`/api/audio/${encodeURIComponent(old.id)}`,{method:'DELETE'}).catch(()=>{});
};
new ResizeObserver(syncTitleStyle).observe($('preview'));
