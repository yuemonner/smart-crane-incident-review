const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const text=(id,value)=>{const el=$(id);if(el)el.textContent=value};
let currentIncident=null;
let loadGeneration=0;
let currentScenario='unexpected';
let rolloutDecisionRecorded=false;
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
if($('livePlay')){$('livePlay').onclick=()=>{livePlaying=!livePlaying;$('livePlay').textContent=livePlaying?'Pause':'Play'};$('liveInject').onclick=()=>{livePlaying=false;$('livePlay').textContent='Play';liveStep=Math.max(liveStep,11);loadLiveReview()};$('liveRestart').onclick=()=>{liveStep=0;livePlaying=true;$('livePlay').textContent='Pause';loadLiveReview()};loadLiveReview().then(liveRun)}

async function loadIncidents(){
  currentScenario=$('scenarioSelect')?.value||'unexpected';
  if(currentScenario==='rollout'){renderRolloutScenario();return}
  renderUnexpectedShell();
  const ticket=++loadGeneration;
  const mode=$('evidenceMode').value;
  const list=await fetch(`/api/incidents?mode=${mode}`).then(r=>r.json());
  if(ticket!==loadGeneration)return;
  $('incidentSelect').innerHTML=list.length?list.map(x=>`<option value="${esc(x.id)}" data-entity="${esc(x.entity_id)}" data-time="${esc(x.incident_time)}">${esc(x.entity_id)} · ${esc(x.title)} · ${new Date(x.incident_time).toLocaleString()}</option>`).join(''):'<option value="">No review triggers in this evidence mode</option>';
  setModeBanner(mode,list.length);
  if(list.length) await loadSelectedIncident(ticket); else clearWorkspace(mode);
}
function renderUnexpectedShell(){
  livePlaying=true;liveStep=0;if($('livePlay')){$('livePlay').textContent='Pause';$('liveInject').textContent='Inject new evidence';}
  document.querySelector('header .crumb').textContent='SMART CRANE · MACHINE DECISION REVIEW SYSTEM';
  document.querySelector('header h1').innerHTML='Crane-07 · Machine Decision Review <em id="lensDescription">director operating picture</em>';
  document.querySelector('.decision-under-review').innerHTML='<b>Decision under review:</b> Continue operating under the current monitoring logic, or revert to the prior alert / hoist profile?';
  document.querySelector('#overview .context-strip').innerHTML='<div><span>Event time</span><b>16:32 UTC</b></div><div><span>High-res window</span><b>16:29-16:32</b></div><div><span>Location</span><b>Site A · Bay 3</b></div><div><span>Load</span><b>87% rated</b></div><div><span>Signal</span><b>1,880 ms latency</b></div>';
  document.querySelector('.overview-grid').innerHTML='<article class="panel summary-card"><span class="eyebrow">TRIGGER</span><strong>E-stop</strong><small>alert delivery behavior under review</small></article><article class="panel summary-card"><span class="eyebrow">EXPOSURE</span><strong id="ovExposed">—</strong><small>same alert logic / hoist profile</small></article><article class="panel summary-card"><span class="eyebrow">BLOCKERS</span><strong id="gapCount">—</strong><small>decision evidence still missing</small></article><article class="panel summary-card"><span class="eyebrow">CURRENT DECISION</span><strong id="decisionStatusShort">PENDING</strong><small id="directorEscalation">Not evaluated</small></article>';
  document.querySelector('.decision-conditions').innerHTML='<span class="eyebrow">CUSTOMER RULE SET</span><h3>Crane operations review policy v3.2</h3><div class="condition-grid"><div><b>Confirmed</b><span>Current alert logic</span></div><div><b>Confirmed</b><span>Last stable hoist profile</span></div><div><b>Confirmed</b><span>High-res event window</span></div><div><b>Confirmed</b><span>Similar crane exposure</span></div><div><b>Confirmed</b><span>Prior profile available</span></div><div class="missing"><b>Not established</b><span>Shared field condition</span></div><div class="missing"><b>Missing</b><span>Alert-delivery verified</span></div></div><small>Checklist configured by Engineering / Safety / Operations. 5 of 7 conditions have supporting evidence. This workspace does not recommend an action.</small>';
  document.querySelector('.director-grid').innerHTML='<article class="panel lkg-card"><span class="eyebrow">LAST KNOWN GOOD</span><div id="lkgState" class="state-pill">NOT ESTABLISHED</div><dl><dt>Observed</dt><dd id="lkgObserved">Not recorded</dd><dt>Software</dt><dd id="lkgSoftware">Not recorded</dd><dt>Configuration</dt><dd id="lkgConfig">Not recorded</dd><dt>Runtime state</dt><dd id="lkgRuntime">Not recorded</dd><dt>Validation</dt><dd id="lkgTests">Not recorded</dd><dt>Validated by</dt><dd id="lkgValidator">Not recorded</dd></dl><small id="lkgLimitation"></small></article><article class="panel scope-card"><span class="eyebrow">EXPOSURE SCOPE</span><div id="scopeState" class="state-pill">NOT ESTABLISHED</div><p id="scopeExplanation">Waiting for comparison evidence.</p><dl><dt>Review-device evidence</dt><dd id="scopeDevice">—</dd><dt>Peer devices with matching signals</dt><dd id="scopeSignals">—</dd><dt>Peer devices with matching alert issues</dt><dd id="scopeIncidents">—</dd></dl><small>Comparison supports review prioritization; it does not establish a shared cause.</small></article>';
  document.querySelector('.memory').innerHTML='<span class="eyebrow">CURRENT HUMAN DECISION</span><p><b>No human decision recorded yet.</b></p><p>When the team records a decision, the workspace freezes the evidence available at that time. Later evidence updates the current view, not the historical decision.</p><div class="memory-grid"><input id="memoryOwner" placeholder="Owner"><input id="memoryCheckpoint" type="datetime-local"><select id="memoryDecision"><option value="">Decision not recorded</option><optgroup label="Record decision"><option>Continue investigation</option><option>Hold current rollout</option><option>Revert to prior profile</option><option>Reapply current profile</option></optgroup><optgroup label="Follow-up"><option>Test again</option></optgroup></select><input id="memoryOutcome" placeholder="Observed outcome after the decision"><button id="saveMemory">Save local record</button></div><small id="memoryMessage"></small>';
  bindMemorySave();
  if($('livePlay')){
    $('liveInject').onclick=()=>{livePlaying=false;$('livePlay').textContent='Play';liveStep=Math.max(liveStep,11);loadLiveReview()};
    $('liveRestart').onclick=()=>{liveStep=0;livePlaying=true;$('livePlay').textContent='Pause';loadLiveReview()};
    loadLiveReview().then(liveRun);
  }
}
function renderRolloutScenario(){
  currentIncident=null;rolloutDecisionRecorded=false;
  clearInterval(liveTimer);livePlaying=false;
  document.querySelector('header .crumb').textContent='SMART CRANE · MACHINE DECISION REVIEW SYSTEM';
  document.querySelector('header h1').innerHTML='Image 0.36 · Machine Decision Review <em id="lensDescription">director operating picture</em>';
  document.querySelector('.decision-under-review').innerHTML='<b>Decision under review:</b> Apply the new monitoring image to the selected cranes, or hold cranes with weak recovery evidence?';
  $('modeBanner').className='mode-banner demo';$('modeBanner').innerHTML='<b>DEMO SCENARIO</b><span>Synthetic pre-deployment rollout review. This workspace does not execute the change.</span>';
  $('incidentSelect').innerHTML='<option>Monitoring image 0.36 · rollout decision · 14/08/2026, 17:05</option>';
  text('freshnessState','SYNTHETIC');text('freshnessDetail','Pre-rollout crane operations review');
  document.querySelector('#overview .context-strip').innerHTML='<div><span>Decision time</span><b>17:05 UTC</b></div><div><span>Cranes selected</span><b>18</b></div><div><span>Image transfer</span><b>4.2 GB</b></div><div><span>Connection path</span><b>7 cellular-only</b></div><div><span>Recovery gaps</span><b>2 cranes</b></div>';
  document.querySelector('.overview-grid').innerHTML='<article class="panel summary-card"><span class="eyebrow">TRIGGER</span><strong>Rollout</strong><small>planned monitoring-image change</small></article><article class="panel summary-card"><span class="eyebrow">CRANES SELECTED</span><strong>18</strong><small>assets in scope</small></article><article class="panel summary-card"><span class="eyebrow">BLOCKERS</span><strong>2</strong><small>cranes missing recovery evidence</small></article><article class="panel summary-card"><span class="eyebrow">CURRENT DECISION</span><strong>PENDING</strong><small>No human decision recorded</small></article>';
  document.querySelector('.decision-conditions').innerHTML='<span class="eyebrow">CUSTOMER RULE SET</span><h3>Rollout review policy v3.2</h3><div class="condition-grid"><div><b>Confirmed</b><span>New monitoring image validated</span></div><div><b>Confirmed</b><span>Transfer integrity available</span></div><div><b>Confirmed</b><span>Previous stable image recorded</span></div><div><b>Confirmed</b><span>Previous rollout outcome</span></div><div class="partial"><b>Partial</b><span>Connection baseline</span></div><div class="missing"><b>Missing</b><span>Recovery path for 2 cranes</span></div><div class="missing"><b>Missing</b><span>Remote-access path for 2 cranes</span></div></div><small>5 of 7 conditions have supporting evidence across the selected cranes. Two cranes do not currently have evidence of a confirmed recovery path. This workspace does not recommend an action.</small>';
  document.querySelector('.director-grid').innerHTML='<article class="panel lkg-card"><span class="eyebrow">LAST KNOWN GOOD</span><div class="state-pill established">ESTABLISHED FROM EVIDENCE</div><dl><dt>Monitoring image</dt><dd>0.35</dd><dt>Prior image</dt><dd>0.35 available for recovery</dd><dt>Validation</dt><dd>Build 2214 passed · transfer check available</dd><dt>History</dt><dd>15 cranes have previous rollout outcomes</dd></dl><small>Last known good is source-linked; it does not prove every selected crane has the same recovery path.</small></article><article class="panel scope-card"><span class="eyebrow">ROLLOUT CONTEXT</span><div class="state-pill observed">PARTIAL COVERAGE</div><p>Same monitoring image. Different site and connection context.</p><dl><dt>Stable + recovery confirmed</dt><dd>11 cranes</dd><dt>Cellular-only</dt><dd>7 cranes</dd><dt>Previous interruptions</dt><dd>3 cranes</dd></dl><small>Comparison supports review prioritization; it does not decide whether rollout should proceed.</small></article>';
  $('escalationTitle').textContent='Two selected cranes block a clean deployment review';
  $('escalationReasons').innerHTML='<li>Crane-11 has no previous large-image rollout history.</li><li>Crane-12 has no confirmed remote-access path.</li><li>Both require recovery-path verification before the decision can be recorded with complete evidence.</li>';
  document.querySelector('.memory').innerHTML='<span class="eyebrow">CURRENT HUMAN DECISION</span><p><b>No human decision recorded yet.</b></p><p>This review happens before the monitoring image is sent. The workspace reconstructs the decision context; the existing update path performs the change only after a human decision is recorded.</p><div class="decision-options rollout-options"><button data-decision="Proceed with 16 selected cranes. Hold Crane-11 and Crane-12 pending recovery-path verification.">Proceed with selected cranes</button><button data-decision="Hold selected cranes pending recovery-path verification.">Hold selected cranes</button><button data-decision="Retry under different connectivity conditions.">Retry under different connectivity conditions</button><button data-decision="Delay rollout.">Delay rollout</button><button data-decision="Cancel rollout.">Cancel rollout</button></div><small id="memoryMessage"></small>';
  document.querySelectorAll('.rollout-options button').forEach(b=>b.onclick=()=>recordRolloutDecision(b.dataset.decision));
  renderRolloutTeamViews(false);
  renderRolloutLive(false);
}
function recordRolloutDecision(decision){
  rolloutDecisionRecorded=true;
  document.querySelector('.memory').innerHTML=`<span class="eyebrow">DECISION RECORDED · 17:05 UTC</span><p><b>${esc(decision)}</b></p><div class="decision-cols"><div><b>Known</b><ul><li>image 0.36 passed build and validation</li><li>checksum available</li><li>image 0.35 rollback package available</li><li>7 selected cranes are cellular-only</li><li>previous rollout outcomes exist for 15 cranes</li></ul></div><div><b>Unknown / missing</b><ul><li>verified recovery path for Crane-11</li><li>verified remote-access path for Crane-12</li></ul></div></div><small>Later evidence may change the current view, but it does not rewrite the evidence available when this decision was made.</small><div class="decision-options"><button id="injectRolloutOutcome">Inject rollout outcome</button></div>`;
  $('injectRolloutOutcome').onclick=()=>{renderRolloutTeamViews(true);renderRolloutLive(true)};
  renderRolloutLive(false);
}
function renderRolloutLive(showOutcome){
  if(!$('livePlay'))return;
  $('liveStep').textContent=showOutcome?'Outcome linked':'Planned rollout review';
  $('livePlay').textContent='Paused';$('liveInject').textContent='Inject rollout outcome';
  $('liveInject').onclick=()=>{if(!rolloutDecisionRecorded)recordRolloutDecision('Proceed with 16 selected cranes. Hold Crane-11 and Crane-12 pending recovery-path verification.');renderRolloutTeamViews(true);renderRolloutLive(true)};
  $('liveRestart').onclick=()=>{rolloutDecisionRecorded=false;renderRolloutScenario()};
  document.querySelector('#live-reconstruction .live-hero h2').textContent='Before rollout → human decision → existing update path → outcome';
  document.querySelector('#live-reconstruction .lede').textContent='Synthetic Smart Crane rollout evidence. The workspace reconstructs decision context before a monitoring image is sent, then observes the outcome and links it back to the original decision.';
  document.querySelector('#live-reconstruction .context-strip').innerHTML='<div><span>Target image</span><b>0.36</b></div><div><span>Cranes selected</span><b>18</b></div><div><span>Transfer size</span><b>4.2 GB</b></div><div><span>Connection path</span><b>7 cellular-only</b></div><div><span>Write access</span><b>None</b></div>';
  $('liveChange').textContent='Monitoring image 0.36 selected for rollout review';$('liveReviewStatus').textContent=rolloutDecisionRecorded?'DECISION RECORDED':'DECISION PENDING';$('liveKnowledgeTime').textContent='17:05';
  const steps=['Monitoring image passed validation','Transfer integrity check available','18 selected cranes loaded from crane inventory','7 selected cranes are cellular-only','3 previous interrupted transfers found','2 recovery paths not established'];
  if(showOutcome)steps.push('Rollout outcome linked to the recorded decision');
  $('liveEvents').innerHTML=steps.map((x,i)=>`<div class="stream-event ${i===steps.length-1?'active':''}"><time>SYNTHETIC · STEP ${i+1}</time><b>${esc(x)}</b><small>read-only source reference · demo data</small></div>`).join('');
  $('liveChanges').innerHTML=[['Monitoring image','0.35','0.36'],['Validation','previous stable image','new image passed review'],['Transfer','current image','4.2 GB target transfer'],['Recovery option','0.35 in service','0.35 available as prior image'],['Access context','not evaluated','2 remote/recovery paths not established']].map(([s,b,a])=>`<div><span>${esc(s)}</span><b>${esc(b)} → ${esc(a)}</b><small>synthetic source evidence · sequence only</small></div>`).join('');
  liveList('liveObserved',['target monitoring image 0.36 selected','new image passed validation','transfer integrity evidence is available','18 selected cranes are in scope','7 selected cranes are cellular-only']);
  liveList('liveHuman',['team intends to review before sending the image to selected cranes','site access constraints should be checked before rollout']);
  liveList('liveInferred',['rollout context differs by crane because connection paths and recovery paths differ','Crane-11 and Crane-12 need additional verification before a clean decision record']);
  liveList('liveNotEstablished',['recovery path for Crane-11','remote-access path for Crane-12','exact connection condition during previous interrupted transfers']);
  liveList('liveInterpretation',['The monitoring image has validation and transfer-integrity evidence.','Most selected cranes have enough supporting context for review.','Two cranes lack recovery/access evidence, so the decision record would contain explicit gaps.']);
  liveList('liveWhy',['Validation and transfer-integrity evidence support the target image.','Crane inventory and connection history establish the selected crane set.','Previous rollout outcomes establish which assets have recovered from similar updates before.']);
  liveList('liveContradicts',['Some cellular-only cranes updated successfully in prior rollouts.','A previous interrupted transfer resumed successfully on Crane-09.','Connectivity-only status does not establish deployment failure.']);
  liveList('liveReduce',['verify recovery path for Crane-11','verify remote-access path for Crane-12','capture transfer interruption markers and post-update reachability checks']);
  document.querySelector('.live-metrics').innerHTML=`<article><span>SELECTED CRANES</span><strong>18</strong><small>assets in scope</small></article><article><span>STABLE + RECOVERY CONFIRMED</span><strong>11</strong><small>selected cranes</small></article><article><span>CELLULAR-ONLY</span><strong>7</strong><small>connection type</small></article><article><span>UNRECOVERABLE DEPLOYMENTS</span><strong>${showOutcome?'0':'—'}</strong><small>${showOutcome?'after outcome injection':'not evaluated yet'}</small></article>`;
  $('liveGaps').innerHTML=[['COMPLETE','monitoring image','current and target images are source-linked'],['COMPLETE','transfer integrity','integrity evidence is available'],['PARTIAL','connection baseline','7 selected cranes are cellular-only'],['MISSING','recovery path','Crane-11 and Crane-12 need verification'],['MISSING','remote access','Crane-12 path is not established']].map(([s,f,e])=>`<div class="${s.toLowerCase()}"><b>${esc(s)}</b><span>${esc(f)}</span><small>${esc(e)}</small></div>`).join('');
  $('liveDecision').innerHTML=rolloutDecisionRecorded?'<h3>Proceed with 16 selected cranes</h3><p>Hold Crane-11 and Crane-12 pending recovery-path verification.</p><div class="decision-cols"><div><b>Known</b><ul><li>monitoring image 0.36 passed validation</li><li>transfer integrity and prior image are available</li><li>7 selected cranes are cellular-only</li></ul></div><div><b>Unknown / missing</b><ul><li>verified recovery path for Crane-11</li><li>verified remote-access path for Crane-12</li></ul></div></div><small>Decision recorded with evidence available at 17:05 UTC.</small>':'<p>No human decision has been recorded yet.</p><div class="decision-options"><span>Proceed with selected cranes</span><span>Hold selected cranes</span><span>Retry under different connection conditions</span><span>Delay rollout</span><span>Cancel rollout</span></div>';
  $('liveLearning').innerHTML=showOutcome?'<h3>Outcome linked to decision</h3><table><tbody><tr><td>Completed normally</td><td>15</td><td>cranes remained reachable after update</td></tr><tr><td>Interrupted and recovered</td><td>1</td><td>cellular transfer resumed</td></tr><tr><td>Held before update</td><td>2</td><td>remained on image 0.35</td></tr><tr><td>Unrecoverable updates</td><td>0</td><td>none recorded</td></tr></tbody></table><p>This rollout outcome becomes context for the next monitoring-image review.</p><small>Historical outcomes are context, not a recommendation.</small>':'<h3>Historical rollout context</h3><p>4 similar previous rollout reviews.</p><table><tbody><tr><td>Proceed with selected cranes</td><td>2</td><td>successful rollout</td></tr><tr><td>Hold selected cranes</td><td>1</td><td>avoided incomplete recovery context</td></tr><tr><td>Retry under different connection conditions</td><td>1</td><td>interrupted but recovered</td></tr></tbody></table><small>Historical outcomes are context, not a recommendation.</small>';
  $('liveNotice').hidden=!showOutcome;$('liveNotice').innerHTML=showOutcome?'<b>Rollout outcome added</b><p>15 cranes completed normally, 1 cellular transfer interrupted and resumed, and 2 held cranes remained on image 0.35.</p><small>This updates the current view without rewriting the decision context recorded at 17:05.</small>':'';
  $('liveBoundary').textContent='Synthetic/demo data only. Read-only evidence workspace: context is reconstructed before the rollout, the existing update path sends the image after human approval, and the outcome is observed afterward. No update execution, VPN management, source writes, or device control.';
}
function renderRolloutTeamViews(showOutcome){
  document.querySelector('#where .hero .eyebrow').textContent='DEPLOYMENT CONTEXT ACROSS SELECTED CRANES';
  document.querySelector('#where .hero h2').textContent='Same software change. Different operational context.';
  document.querySelector('#where .lede').textContent='Compare selected cranes before the image is sent and before a human proceed / hold / retry decision is recorded.';
  document.querySelector('#where .context-strip').innerHTML='<div><span>Selected cranes</span><b>18</b></div><div><span>Stable + recovery</span><b>11</b></div><div><span>Cellular-only</span><b>7</b></div><div><span>Interrupted before</span><b>3</b></div><div><span>Recovery missing</span><b>2</b></div>';
  document.querySelector('#where .metrics').innerHTML='<article><span>SELECTED CRANES</span><strong>18</strong><small>assets in scope</small></article><article><span>STABLE + RECOVERY CONFIRMED</span><strong>11</strong><small>selected cranes</small></article><article><span>CELLULAR-ONLY</span><strong>7</strong><small>connection type</small></article><article><span>RECOVERY PATH MISSING</span><strong>2</strong><small>decision blockers</small></article>';
  $('matches').innerHTML=[
    ['Crane-08','Site A','Cellular','Previous large update successful','Recovery path confirmed','CONFIRMED'],
    ['Crane-09','Site B','Cellular','Previous transfer interrupted and resumed','Recovery path confirmed','PARTIAL'],
    ['Crane-10','Site C','Wired','Previous update successful','Recovery path confirmed','CONFIRMED'],
    ['Crane-11','Site B','Cellular','No previous large-image rollout history','Recovery path not established','NOT ESTABLISHED'],
    ['Crane-12','Site C','Cellular','Remote-access path not established','Recovery path not established','MISSING'],
  ].map(a=>`<div class="match"><div><b>${a[0]}</b><small>${a[1]} · ${a[2]} · ${a[3]} · ${a[4]}</small></div><span class="tag ${a[5]==='MISSING'?'hot':''}">${a[5]}</span><span class="score">review</span></div>`).join('')+'<div class="match-more">+13 additional selected cranes</div>';
  setList('confirmed',['18 selected cranes are in scope.','11 have stable connection history and recovery path confirmed.','monitoring image 0.36 validation, transfer check and prior-image evidence are available.']);
  setList('unknown',['Recovery path is not established for Crane-11 and Crane-12.','Remote-access path is not established for Crane-12.']);
  setList('gaps',['Exact connectivity condition during prior interrupted transfer.','Site-specific access constraint as understood at decision time.']);
  document.querySelector('#changed .context-strip').innerHTML='<div><span>Current image</span><b>0.35</b></div><div><span>Target image</span><b>0.36</b></div><div><span>Validation</span><b>Passed</b></div><div><span>Transfer size</span><b>4.2 GB</b></div><div><span>Integrity check</span><b>Available</b></div>';
  $('changes').innerHTML=[['Monitoring image','0.35','0.36'],['Validation','previous stable image','new image passed review'],['Transfer','current runtime image','4.2 GB image transfer'],['Integrity','not required for current state','transfer check available'],['Recovery option','image 0.35 installed','image 0.35 available as prior stable image'],['Evidence sources','single rollout manifest','build record · manifest · inventory · connection history · site access policy · rollout history']].map(([l,b,a])=>`<article class="diffrow"><span>${esc(l)}</span><div><small>CURRENT / EVIDENCE</small><b>${esc(b)}</b></div><i>→</i><div><small>TARGET / SUPPORTING CONTEXT</small><b>${esc(a)}</b></div></article>`).join('');
  $('timeline').innerHTML=['Build record · monitoring image passed validation','Rollout manifest · image 0.36 selected','Crane inventory · 18 selected cranes in scope','Connection history · 7 cellular-only','Remote-access record · 2 paths not established','Previous rollout outcomes · 3 prior interrupted transfers'].map((x,i)=>`<div class="event supporting observed"><time>SYNTHETIC · SOURCE ${i+1}</time><b>${esc(x)}</b><div class="metric-row"><span>demo data</span><span>read-only</span></div><small class="evidence-meta">OBSERVED · SOURCE REFERENCE · DEMO</small></div>`).join('');
  setList('provenanceLimits',['Synthetic/demo data only.','Decision context only: no update execution, no VPN management, no device control.']);
  setList('alreadyReconstructable',['monitoring image version','build and validation result','transfer integrity check','device connection type','rollout timestamp','previous rollout outcome']);
  setList('notReconstructable',['exact connectivity condition during an interrupted transfer','why a manual retry was initiated','recovery method actually used','site-specific access constraint as understood at decision time']);
  setList('captureNextTime',['transfer start / completion / interruption markers','connectivity snapshot during deployment','confirmed recovery path per crane','human retry reason','post-deployment reachability check','outcome linked to the original rollout decision']);
  if(showOutcome){
    document.querySelector('.learning-panel')?.removeAttribute('hidden');
    $('liveLearning').innerHTML='<h3>Outcome linked to decision</h3><table><tbody><tr><td>Completed normally</td><td>15</td><td>cranes remained reachable after update</td></tr><tr><td>Interrupted and recovered</td><td>1</td><td>cellular transfer resumed</td></tr><tr><td>Held before update</td><td>2</td><td>remained on image 0.35</td></tr><tr><td>Unrecoverable updates</td><td>0</td><td>none recorded</td></tr></tbody></table><p>This rollout outcome becomes context for the next monitoring-image review.</p><small>Historical outcomes are context, not a recommendation.</small>';
  }
}
function setModeBanner(mode,count){
  const copy={demo:['DEMO SCENARIO','Synthetic records only. No production evidence is shown.'],live:['LIVE EVIDENCE','Only live source records are shown.'],cached:['CACHED EVIDENCE','Saved source snapshot only; freshness is explicit.'],partial:['PARTIAL EVIDENCE','Incomplete source set only; gaps must be reviewed.']}[mode];
  $('modeBanner').className=`mode-banner ${mode==='live'?'live-mode':mode}`;$('modeBanner').innerHTML=`<b>${copy[0]}</b><span>${copy[1]} · ${count} selectable review trigger${count===1?'':'s'}</span>`;
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
  if($('timeline'))$('timeline').innerHTML=`<div class="panel">No ${esc(mode)} review evidence is currently loaded. Connect or refresh the relevant read-only source; synthetic evidence will not be substituted.</div>`;
  if($('matches'))$('matches').innerHTML='';if($('customerExposure'))$('customerExposure').innerHTML='<p>No evidence loaded in this mode.</p>';if($('attentionState'))$('attentionState').textContent='NO EVIDENCE';if($('escalationTitle'))$('escalationTitle').textContent='Director-attention rules were not evaluated';if($('escalationReasons'))$('escalationReasons').innerHTML='<li>No review evidence is loaded in this workspace.</li>';if($('confirmed'))$('confirmed').innerHTML='';if($('unknown'))$('unknown').innerHTML='';if($('gaps'))$('gaps').innerHTML='';if($('changes'))$('changes').innerHTML='';if($('provenanceLimits'))$('provenanceLimits').innerHTML='<li>No evidence loaded.</li>';if($('freshnessState'))$('freshnessState').textContent='NO EVIDENCE';if($('freshnessDetail'))$('freshnessDetail').textContent='Nothing from another mode is being mixed in.';
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
    'alert delivery retry-handling or profile change may be related',
    'alert logic / hoist profile C17 may be part of the exposure surface',
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
async function loadMemory(){if(!currentIncident||!$('memoryOutcome'))return;const r=await fetch(`/api/memory/incidents/${encodeURIComponent(currentIncident.id)}`);if(!r.ok){text('recordedDecision','Pending team decision');$('memoryOutcome').value='';return}const m=await r.json();$('memoryOwner').value=m.owner||'';$('memoryCheckpoint').value=m.checkpoint_at?m.checkpoint_at.slice(0,16):'';$('memoryDecision').value=m.decision||'';$('memoryOutcome').value=m.outcome||'';text('incidentOwner',m.owner||$('incidentOwner')?.textContent||'Not recorded');text('checkpointDue',m.checkpoint_at?new Date(m.checkpoint_at).toLocaleString():$('checkpointDue')?.textContent||'Not recorded');text('recordedDecision',m.decision?(m.outcome?`${m.decision} · outcome: ${m.outcome}`:m.decision):'Pending team decision')}
function bindMemorySave(){if(!$('saveMemory'))return;$('saveMemory').onclick=async()=>{if(!currentIncident)return;const q=currentIncident.request,i=currentIncident.investigation,now=new Date().toISOString(),decision=$('memoryDecision').value||null,p={id:currentIncident.id,entity_id:q.entity_id,title:currentIncident.title,incident_time:q.incident_time,owner:$('memoryOwner').value||null,checkpoint_at:$('memoryCheckpoint').value?new Date($('memoryCheckpoint').value).toISOString():null,decision,decision_at:decision?now:null,outcome:$('memoryOutcome').value||null,outcome_recorded_at:$('memoryOutcome').value?now:null,knowledge_at_decision:decision?{captured_at:now,observed:i.status.confirmed,evidence_supported:[i.scope_assessment?.explanation].filter(Boolean),assumptions:[],unknowns:[...i.status.not_established,...i.status.evidence_gaps],evidence_ids:i.timeline.map(e=>e.id)}:null};const r=await fetch(`/api/memory/incidents/${encodeURIComponent(p.id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});$('memoryMessage').textContent=r.ok?'Decision, evidence available at the time, and outcome preserved locally. No source system was changed.':'Could not save the local record.';if(r.ok)await loadMemory()};}
bindMemorySave();$('scenarioSelect').onchange=loadIncidents;$('evidenceMode').onchange=loadIncidents;$('incidentSelect').onchange=loadSelectedIncident;loadIncidents().catch(e=>clearWorkspace($('evidenceMode').value));
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button,.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.view).classList.add('active')});
document.querySelectorAll('.role-switch button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.role-switch button').forEach(x=>x.classList.remove('active'));b.classList.add('active');const d=b.dataset.role==='director';$('lensDescription').textContent=d?'director operating picture':'team review workspace';document.querySelector(`nav button[data-view="${d?'overview':'where'}"]`).click();document.body.dataset.lens=b.dataset.role});
