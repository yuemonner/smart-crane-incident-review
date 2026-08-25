const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const text=(id,value)=>{const el=$(id);if(el)el.textContent=value};
let currentIncident=null;
let loadGeneration=0;
const physical=e=>e.type==='alarm'||e.type==='device_event'||e.attributes?.physical_signal;
const setList=(id,items)=>{const el=$(id);if(el)el.innerHTML=(items||[]).map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Not recorded in this evidence set.</li>'};
const metricChips=e=>[
  e.attributes?.site&&`site ${e.attributes.site}`,
  e.attributes?.zone,
  e.attributes?.load_pct!=null&&`load ${e.attributes.load_pct}%`,
  (e.attributes?.value_ms??e.attributes?.latency_ms)!=null&&`latency ${e.attributes.value_ms??e.attributes.latency_ms} ms`,
  e.attributes?.capture_window&&`${e.attributes.capture_window}`,
  e.attributes?.sample_rate_hz!=null&&`${e.attributes.sample_rate_hz} Hz`,
  e.attributes?.successful_test_cycles!=null&&`${e.attributes.successful_test_cycles} cycles`,
].filter(Boolean).map(x=>`<span>${esc(x)}</span>`).join('');
const eventCard=e=>{const metrics=metricChips(e);return `<div class="event ${physical(e)?'physical':'supporting'} ${esc(e.assertion_kind||'observed')}"><time>${new Date(e.occurred_at).toLocaleString()} · ${esc(e.type).toUpperCase()}</time><b>${esc(e.title)}</b>${metrics?`<div class="metric-row">${metrics}</div>`:''}<a href="${esc(e.source_url||'#')}" target="_blank">${esc(e.source)} · ${esc(e.id)} ↗</a><small class="evidence-meta">${esc(e.assertion_kind||'observed').toUpperCase()} · ${esc(e.capture_class||'source_reference').replaceAll('_',' ').toUpperCase()}${e.confidence!=null?` · confidence ${Math.round(e.confidence*100)}%`:''} · ${esc(e.evidence_mode).toUpperCase()} · retrieved ${e.retrieved_at?new Date(e.retrieved_at).toLocaleString():'not recorded'} · ${esc(e.integrity?.transport||'transport not recorded')}</small></div>`};
let liveStep=0,liveMax=10,livePlaying=true,liveTimer=null;
const liveList=(id,items)=>{const el=$(id);if(el)el.innerHTML=(items||[]).map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Not available yet.</li>'};
const liveRun=()=>{clearInterval(liveTimer);liveTimer=setInterval(()=>{if(!livePlaying)return;liveStep=liveStep>=liveMax?0:liveStep+1;loadLiveReview()},2200)};
async function loadLiveReview(){
  const data=await fetch(`/api/reconstruction/live-demo?step=${liveStep}`).then(r=>r.json());
  liveMax=data.max_step;$('liveStep').textContent=`Step ${data.step} / ${data.max_step}`;$('liveKnowledgeTime').textContent=new Date(data.knowledge_time).toLocaleTimeString();
  const active=data.active_event;$('liveChange').textContent=active.title;$('liveReviewStatus').textContent=data.new_review.created?data.new_review.status:'Not created';
  $('liveEvents').innerHTML=data.event_stream.map(e=>`<div class="stream-event ${e.index===data.step?'active':''}"><time>${new Date(e.event_time).toLocaleString()}</time><b>${esc(e.title)}</b><small>${esc(e.source)} · ${esc(e.reconstruction_note)}</small></div>`).join('');
  $('liveChanges').innerHTML=(data.reconstruct_what_changed||[]).slice(0,6).map(c=>`<div><span>${esc(c.subject)}</span><b>${esc(c.before||'—')} → ${esc(c.after||'—')}</b><small>${esc(c.source_system)} · ${new Date(c.event_time).toLocaleString()} · ${esc(c.evidence_strength)}</small></div>`).join('')||'<p>No changes reconstructed yet.</p>';
  liveList('liveObserved',data.evidence_state.observed);liveList('liveHuman',data.evidence_state.human_asserted);liveList('liveInferred',data.evidence_state.inferred);liveList('liveNotEstablished',data.evidence_state.not_established);
  liveList('liveInterpretation',data.ai_reasoning_layer.current_interpretation);liveList('liveWhy',data.ai_reasoning_layer.why);liveList('liveContradicts',data.ai_reasoning_layer.what_contradicts_this);liveList('liveReduce',data.ai_reasoning_layer.what_would_reduce_uncertainty);
  $('liveExposed').textContent=data.where_else.exposed_count;$('livePrecursors').textContent=data.where_else.precursor_count;$('liveCounterexamples').textContent=data.where_else.counterexample_count;$('liveFailures').textContent=data.where_else.matching_failure_count;
  $('liveGaps').innerHTML=data.reconstructability.coverage.map(x=>`<div class="${esc(x.state).toLowerCase()}"><b>${esc(x.state)}</b><span>${esc(x.field)}</span><small>${esc(x.explanation)}</small></div>`).join('');
  const decision=data.team_decision.recorded;$('liveDecision').innerHTML=decision?`<h3>${esc(decision.decision)}</h3><p><b>Decision time:</b> ${new Date(decision.decision_time).toLocaleString()}</p><p><b>Evidence available:</b> ${decision.evidence_available_count} records</p><div class="decision-cols"><div><b>Known</b><ul>${decision.known.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div><div><b>Unknown</b><ul>${decision.unknown.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div><small>${esc(decision.historical_context_rule)}</small>`:`<p>No human decision has been recorded yet.</p><div class="decision-options">${data.team_decision.options.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`;
  const learning=data.historical_learning;$('liveLearning').innerHTML=learning.created?`<h3>${esc(learning.headline)}</h3><p>${esc(learning.similar_contexts)} similar historical contexts found.</p><table><thead><tr><th>Previous action</th><th>Cases</th><th>Outcome</th></tr></thead><tbody>${learning.outcomes.map(x=>`<tr><td>${esc(x.previous_action)}</td><td>${esc(x.cases)}</td><td>${esc(x.outcome)}</td></tr>`).join('')}</tbody></table><small>${esc(learning.note)}</small>`:`<p>${esc(learning.note)}</p><div class="decision-options"><span>Similar cases pending</span><span>Outcomes pending</span><span>Not a recommendation</span></div>`;
  const notice=data.new_evidence_notice;$('liveNotice').hidden=!notice;$('liveNotice').innerHTML=notice?`<b>${esc(notice.title)}</b><p>${esc(notice.message)}</p><small>${esc(notice.historical_context)}</small>`:'';
  $('liveBoundary').textContent=data.data_boundary;
}
if($('livePlay')){$('livePlay').onclick=()=>{livePlaying=!livePlaying;$('livePlay').textContent=livePlaying?'Pause':'Play'};$('liveInject').onclick=()=>{livePlaying=false;$('livePlay').textContent='Play';liveStep=Math.max(liveStep,10);loadLiveReview()};$('liveRestart').onclick=()=>{liveStep=0;livePlaying=true;$('livePlay').textContent='Pause';loadLiveReview()};loadLiveReview().then(liveRun)}

async function loadIncidents(){
  const ticket=++loadGeneration;
  const mode=$('evidenceMode').value;
  const list=await fetch(`/api/incidents?mode=${mode}`).then(r=>r.json());
  if(ticket!==loadGeneration)return;
  $('incidentSelect').innerHTML=list.length?list.map(x=>`<option value="${esc(x.id)}" data-entity="${esc(x.entity_id)}" data-time="${esc(x.incident_time)}">${esc(x.entity_id)} · ${esc(x.title)} · ${new Date(x.incident_time).toLocaleString()}</option>`).join(''):'<option value="">No incidents in this evidence mode</option>';
  setModeBanner(mode,list.length);
  if(list.length) await loadSelectedIncident(ticket); else clearWorkspace(mode);
}
function setModeBanner(mode,count){
  const copy={demo:['DEMO SCENARIO','Synthetic records only. No production evidence is shown.'],live:['LIVE EVIDENCE','Only live source records are shown.'],cached:['CACHED EVIDENCE','Saved source snapshot only; freshness is explicit.'],partial:['PARTIAL EVIDENCE','Incomplete source set only; gaps must be reviewed.']}[mode];
  $('modeBanner').className=`mode-banner ${mode==='live'?'live-mode':mode}`;$('modeBanner').innerHTML=`<b>${copy[0]}</b><span>${copy[1]} · ${count} selectable incident${count===1?'':'s'}</span>`;
}
async function loadSelectedIncident(ticket=++loadGeneration){
  const option=$('incidentSelect').selectedOptions[0]; if(!option?.value)return;
  const req={entity_id:option.dataset.entity,incident_time:option.dataset.time,window_hours:72,evidence_mode:$('evidenceMode').value};
  const [i,w]=await Promise.all([
    fetch('/api/incidents/investigate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)}).then(r=>r.json()),
    fetch('/api/incidents/where-else',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)}).then(r=>r.json())]);
  if(ticket!==loadGeneration)return;
  currentIncident={id:option.value,title:option.textContent,request:req,investigation:i};render(i,w);await loadMemory();
}
function clearWorkspace(mode){
  currentIncident=null;['exposed','precursors','customers','ovExposed','ovSignals','reviewCount','gapCount'].forEach(id=>text(id,'—'));
  text('decisionStatusShort','PENDING');
  if($('timeline'))$('timeline').innerHTML=`<div class="panel">No ${esc(mode)} incident evidence is currently loaded. Connect or refresh the relevant read-only source; synthetic evidence will not be substituted.</div>`;
  if($('matches'))$('matches').innerHTML='';if($('customerExposure'))$('customerExposure').innerHTML='<p>No evidence loaded in this mode.</p>';if($('attentionState'))$('attentionState').textContent='NO EVIDENCE';if($('escalationTitle'))$('escalationTitle').textContent='Director-attention rules were not evaluated';if($('escalationReasons'))$('escalationReasons').innerHTML='<li>No incident evidence is loaded in this workspace.</li>';if($('confirmed'))$('confirmed').innerHTML='';if($('unknown'))$('unknown').innerHTML='';if($('gaps'))$('gaps').innerHTML='';if($('changes'))$('changes').innerHTML='';if($('provenanceLimits'))$('provenanceLimits').innerHTML='<li>No evidence loaded.</li>';if($('freshnessState'))$('freshnessState').textContent='NO EVIDENCE';if($('freshnessDetail'))$('freshnessDetail').textContent='Nothing from another mode is being mixed in.';
  text('directorEscalation','Not evaluated');
  ['ksObserved','ksSuspected','ksUnknown','ksCounter','alreadyReconstructable','notReconstructable','captureNextTime'].forEach(id=>setList(id,[]));
  $('lkgState').textContent='NOT ESTABLISHED';$('lkgObserved').textContent=$('lkgSoftware').textContent=$('lkgConfig').textContent=$('lkgRuntime').textContent=$('lkgTests').textContent=$('lkgValidator').textContent='Not recorded';$('scopeState').textContent='NOT ESTABLISHED';$('scopeExplanation').textContent='No decision review evidence is loaded.';$('scopeDevice').textContent=$('scopeSignals').textContent=$('scopeIncidents').textContent='—';
}
function render(i,w){
  $('exposed').textContent=w.exposed_count;$('precursors').textContent=w.precursor_count;$('customers').textContent=w.customer_count;
  text('ovExposed',w.exposed_count);text('ovSignals',w.precursor_count);text('reviewCount',w.precursor_count);text('gapCount',w.status.evidence_gaps.length);text('decisionStatusShort','PENDING');
  const customerCounts=w.matches.reduce((a,m)=>(a[m.customer]=(a[m.customer]||0)+1,a),{});if($('customerExposure'))$('customerExposure').innerHTML=Object.keys(customerCounts).length?Object.entries(customerCounts).map(([n,c])=>`<p><b>${c}</b> ${esc(n)}</p>`).join(''):'<p>No cross-fleet customer exposure established from this evidence set.</p>';
  renderKnowledgeState(i,w);renderReconstructability(i,w);
  const c=i.coordination||{};text('incidentOwner',c.owner||'Not recorded');text('adoState',c.state||'No linked ADO work item');text('investigationTask',c.work_item_id?`ADO ${c.work_item_id}`:'Not recorded');text('checkpointDue',c.checkpoint_at?new Date(c.checkpoint_at).toLocaleString():'Not recorded');
  const l=i.last_known_good||{};$('lkgState').textContent=l.established?'ESTABLISHED FROM EVIDENCE':'NOT ESTABLISHED';$('lkgState').className=`state-pill ${l.established?'established':''}`;$('lkgObserved').textContent=l.observed_at?new Date(l.observed_at).toLocaleString():'Not recorded';$('lkgSoftware').textContent=l.software_revision||'Not recorded';$('lkgConfig').textContent=l.config_profile||'Not recorded';$('lkgRuntime').textContent=l.runtime_state||'Not recorded';$('lkgTests').textContent=l.test_evidence?.join(' · ')||'Not recorded';$('lkgValidator').textContent=l.validated_by||'Not recorded';$('lkgLimitation').textContent=l.limitation||'';
  const s=i.scope_assessment||{};$('scopeState').textContent=(s.classification||'not_established').replaceAll('_',' ').toUpperCase();$('scopeState').className=`state-pill ${s.classification!=='not_established'?'observed':''}`;$('scopeExplanation').textContent=s.explanation||'Not established';$('scopeDevice').textContent=s.device_evidence_count??'—';$('scopeSignals').textContent=s.peer_signal_count??'—';$('scopeIncidents').textContent=s.peer_incident_count??'—';
  const escalated=w.customer_count>1&&w.precursor_count>0;$('attentionState').textContent=escalated?'RULE MATCHED':'NO RULE MATCHED';text('directorEscalation',escalated?'Required under current rules':'Not required under current rules');$('escalationTitle').textContent=escalated?'Explicit review-escalation rule matched':'No review-escalation rule matched';$('escalationReasons').innerHTML=escalated?`<li>Matching telemetry is present on ${w.precursor_count} peer assets.</li><li>Exposed assets span ${w.customer_count} customer fleets.</li><li>Root cause remains not established.</li>`:'<li>No configured threshold is currently met.</li>';
  $('noSignal').textContent=$('noSignalCopy').textContent=Math.max(0,w.exposed_count-w.precursor_count);
  const topMatches=w.matches.slice(0,5),remaining=Math.max(0,w.matches.length-topMatches.length);
  $('matches').innerHTML=topMatches.map(m=>`<div class="match"><div><b>${esc(m.entity_id)}</b><small>${esc(m.customer)} · ${esc(m.matched_factors.join(' · '))}</small></div><span class="tag ${m.precursor_detected?'hot':''}">${m.precursor_detected?'HIGH PRIORITY':'REVIEW'}</span><span class="score">${m.matched_factors.length}/3 signals</span></div>`).join('')+(remaining?`<div class="match-more">+${remaining} additional exposed assets</div>`:'');
  for(const [id,list] of [['confirmed',w.status.confirmed],['unknown',w.status.not_established],['gaps',w.status.evidence_gaps]])$(id).innerHTML=list.map(x=>`<li>${esc(x)}</li>`).join('');
  const ordered=[...i.timeline].sort((a,b)=>(physical(b)?1:0)-(physical(a)?1:0)||new Date(a.occurred_at)-new Date(b.occurred_at));$('timeline').innerHTML=ordered.map(eventCard).join('');renderDiff(i);
  const limits=[...new Set(i.timeline.map(e=>e.integrity?.limitation).filter(Boolean))];$('provenanceLimits').innerHTML=limits.map(x=>`<li>${esc(x)}</li>`).join('')||'<li>No integrity statement was recorded for this evidence.</li>';
  const newest=i.freshest_source_at,oldest=i.stalest_source_at;$('freshnessState').textContent=i.evidence_mode.toUpperCase();$('freshnessDetail').textContent=newest?`Retrieved ${new Date(newest).toLocaleString()}${oldest&&oldest!==newest?` · oldest retrieval ${new Date(oldest).toLocaleString()}`:''}`:'Retrieval timestamp not recorded.';
}
function renderKnowledgeState(i,w){
  const deployment=i.timeline.find(e=>e.type==='deployment'), alarm=i.timeline.find(e=>e.type==='alarm');
  setList('ksObserved',[
    alarm?`${alarm.title.replace(' event with alert-delivery behavior under review','')} during operation; alert delivery behavior is under review.`:'Alarm evidence is not present',
    deployment?`${deployment.attributes?.firmware||'software'} active in the review window`:'Active software revision is not established',
    i.status.confirmed.find(x=>x.includes('alert'))||'Email/text alert acknowledgement status requires review',
  ]);
  setList('ksSuspected',[
    'alert delivery retry-handling or monitoring config change may be related',
    'alert routing config C17 may be part of the exposure surface',
  ]);
  setList('ksUnknown',[
    ...i.status.not_established,
    'whether the same machine state existed on every peer asset',
  ]);
  const noSignal=Math.max(0,w.exposed_count-w.precursor_count);
  setList('ksCounter',[
    `${noSignal} exposed assets show no matching signal`,
    `${w.matches.filter(m=>!m.precursor_detected).length} reviewed peer records do not establish a matching alert-delivery issue`,
    'sequence does not establish causality',
  ]);
}
function renderReconstructability(i,w){
  const l=i.last_known_good||{};
  setList('alreadyReconstructable',[
    l.software_revision?`software revision ${l.software_revision}`:'software revision when deployment evidence exists',
    l.config_profile?`configuration ${l.config_profile}`:'configuration when source record exists',
    i.timeline.some(e=>e.type==='alarm')?'alarm event and timestamp':'alarm event when source record exists',
    i.timeline.some(e=>e.attributes?.capture_window)?'3-minute high-resolution event window':'high-resolution event window when capture exists',
    l.test_evidence?.length?l.test_evidence.join(' · '):'test result when validation marker exists',
  ]);
  setList('notReconstructable',[
    'operator override reason',
    'machine and alert-delivery state immediately around E-stop',
    'exact config diff across every affected module',
    'intervention start/end boundaries',
    'local state during connectivity loss',
  ]);
  setList('captureNextTime',[
    'lightweight runtime trace around critical triggers',
    'critical-event snapshot of software/config/runtime state',
    'append-only intervention record with reason and time window',
    'explicit last-known-good marker after validation',
    'source-linked decision record with outcome follow-up',
  ]);
}
function renderDiff(i){const c=i.what_changed,d=c.find(e=>e.type==='deployment'),cfg=c.find(e=>e.type==='config_change'),commit=c.find(e=>e.type==='commit'),build=c.find(e=>e.type==='build'),tests=c.filter(e=>e.type==='test'),signals=i.timeline.filter(physical);const elapsed=e=>d&&e?`${((new Date(e.occurred_at)-new Date(d.occurred_at))/36e5).toFixed(1)}h after deployment`:'Not established';const rows=[['Monitoring software version',d?.attributes?.previous_firmware||'Not in evidence',d?.attributes?.firmware||'Not in evidence'],['Alert routing configuration',cfg?.attributes?.previous||'Not in evidence',cfg?.attributes?.config_profile||'Not in evidence'],['Notification handling',commit?.attributes?.commit||commit?.id||'Not in evidence',commit?.title||'No linked change'],['Validation',build?.title||'Build evidence unavailable',tests.length?tests.map(x=>x.title).join(' · '):'Test evidence unavailable'],['First alert-delivery signal','—',elapsed(signals[0])],['Trigger','—',elapsed(signals.find(e=>e.type==='alarm'))],['Causal link','—','Not established']];$('changes').innerHTML=rows.map(([l,b,a])=>`<article class="diffrow"><span>${esc(l)}</span><div><small>BEFORE / EVIDENCE</small><b>${esc(b)}</b></div><i>→</i><div><small>AFTER / OBSERVATION</small><b>${esc(a)}</b></div></article>`).join('')}
async function loadMemory(){if(!currentIncident)return;const r=await fetch(`/api/memory/incidents/${encodeURIComponent(currentIncident.id)}`);if(!r.ok){text('recordedDecision','Pending team decision');$('memoryOutcome').value='';return}const m=await r.json();$('memoryOwner').value=m.owner||'';$('memoryCheckpoint').value=m.checkpoint_at?m.checkpoint_at.slice(0,16):'';$('memoryDecision').value=m.decision||'';$('memoryOutcome').value=m.outcome||'';text('incidentOwner',m.owner||$('incidentOwner')?.textContent||'Not recorded');text('checkpointDue',m.checkpoint_at?new Date(m.checkpoint_at).toLocaleString():$('checkpointDue')?.textContent||'Not recorded');text('recordedDecision',m.decision?(m.outcome?`${m.decision} · outcome: ${m.outcome}`:m.decision):'Pending team decision')}
$('saveMemory').onclick=async()=>{if(!currentIncident)return;const q=currentIncident.request,i=currentIncident.investigation,now=new Date().toISOString(),decision=$('memoryDecision').value||null,p={id:currentIncident.id,entity_id:q.entity_id,title:currentIncident.title,incident_time:q.incident_time,owner:$('memoryOwner').value||null,checkpoint_at:$('memoryCheckpoint').value?new Date($('memoryCheckpoint').value).toISOString():null,decision,decision_at:decision?now:null,outcome:$('memoryOutcome').value||null,outcome_recorded_at:$('memoryOutcome').value?now:null,knowledge_at_decision:decision?{captured_at:now,observed:i.status.confirmed,evidence_supported:[i.scope_assessment?.explanation].filter(Boolean),assumptions:[],unknowns:[...i.status.not_established,...i.status.evidence_gaps],evidence_ids:i.timeline.map(e=>e.id)}:null};const r=await fetch(`/api/memory/incidents/${encodeURIComponent(p.id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});$('memoryMessage').textContent=r.ok?'Decision, evidence available at the time, and outcome preserved locally. No source system was changed.':'Could not save the local record.';if(r.ok)await loadMemory()};
$('evidenceMode').onchange=loadIncidents;$('incidentSelect').onchange=loadSelectedIncident;loadIncidents().catch(e=>clearWorkspace($('evidenceMode').value));
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button,.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.view).classList.add('active')});
document.querySelectorAll('.role-switch button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.role-switch button').forEach(x=>x.classList.remove('active'));b.classList.add('active');const d=b.dataset.role==='director';$('lensDescription').textContent=d?'director operating picture':'team review workspace';document.querySelector(`nav button[data-view="${d?'overview':'where'}"]`).click();document.body.dataset.lens=b.dataset.role});
