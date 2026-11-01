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
