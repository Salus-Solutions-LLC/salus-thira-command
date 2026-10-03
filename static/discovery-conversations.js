'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {thread: null, parent: null, profile: null, reviewer: false, busy: false,
    threadsAfter: '', perspectivesAfter: '', mineAfter: '', reviewAfter: '', candidatesAfter: '', keys: {}};
  const text = (tag, value, cls) => {const e = document.createElement(tag); e.textContent = value; if (cls) e.className = cls; return e;};
  const button = (label, fn) => {const e = text('button', label); e.type = 'button'; e.addEventListener('click', () => action(fn)); return e;};
  const key = () => crypto.randomUUID().replaceAll('-', '');
  const date = value => new Intl.DateTimeFormat('en-GB', {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'UTC'}).format(new Date(value)) + ' UTC';
  function announce(value) {$('status').textContent = value; $('error').hidden = true;}
  function failure(error) {$('error').textContent = error.message; $('error').hidden = false; $('error').focus();}
  async function api(path, method='GET', body) {
    const response = await fetch('/api/discovery' + path, {method, credentials:'same-origin',
      headers: method === 'GET' ? {} : {'Content-Type':'application/json','X-Salus-Discovery':'1'},
      body: body === undefined ? undefined : JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(response.status === 401 ? 'Sign in with an approved Salus account, then return to this page.' : typeof data.detail === 'string' ? data.detail : 'Check the form fields and try again.');
      error.status = response.status; throw error;
    }
    return data;
  }
  async function action(fn) {
    if (state.busy) return;
    state.busy = true;
    try {await fn();} catch(e) {failure(e);} finally {state.busy = false;}
  }
  function bind(formId, fn) {$(formId).addEventListener('submit', event => {event.preventDefault(); action(fn);});}
  function more(id, cursor, fn) {$(id).hidden = !cursor; $(id).onclick = () => action(fn);}
  function card(row) {
    const e = text('article', '', 'card');
    e.append(text('h3', row.public_name), text('p', `${row.prompt} · ${date(row.created_at)}${row.updated_at !== row.created_at ? ' · Updated ' + date(row.updated_at) : ''}`, 'meta'), text('p', row.body, 'body'));
    return e;
  }
  async function threads(reset=false) {
    if (reset) {state.threadsAfter=''; $('threads').replaceChildren();}
    const data = await api('/threads?after=' + encodeURIComponent(state.threadsAfter));
    if (reset && !data.items.length) $('threads').append(text('p', 'No conversations have been published yet. Your Discovery Question can help us begin.'));
    data.items.forEach(row => {
      const e = text('article', '', 'card');
      e.append(text('p', row.kind === 'Insight' ? 'SALUS INSIGHTS' : 'DISCOVERY QUESTION', 'eyebrow'), text('h3', row.title), button('Explore this conversation', () => select(row.id)));
      $('threads').append(e);
    });
    state.threadsAfter=data.next || ''; more('more-threads', data.next, () => threads());
  }
  async function select(id) {
    state.parent=null; state.perspectivesAfter='';
    $('reply-context').hidden=true; $('clear-reply').hidden=true;
    $('perspectives').replaceChildren();
    const data = await api('/threads/' + encodeURIComponent(id));
    state.thread=data.thread;
    $('conversation').hidden=false; $('conversation-title').textContent=data.thread.title;
    $('source').replaceChildren();
    if (data.thread.source_url) {
      const a = text('a', 'Read the Salus Insight'); a.href=data.thread.source_url;
      $('source').append(a, text('span', ' · Source version ' + data.thread.source_version));
    }
    $('closed').hidden=Boolean(data.thread.open);
    $('selected-thread').textContent='Your perspective on: ' + data.thread.title;
    $('submit-perspective').disabled=!data.thread.open;
    renderPerspectives(data);
    $('conversation-title').focus();
    if (state.reviewer) {
      $('source').append(button(data.thread.open ? 'Close this conversation' : 'Reopen this conversation', async () => {
        const reason = window.prompt('Record the reason for this conversation change.'); if (!reason) return;
        await api('/threads/' + id + '/state','POST',{open:!data.thread.open,reason}); await select(id);
      }));
    }
    history.replaceState(null,'','#conversation=' + encodeURIComponent(id));
  }
  function renderPerspectives(data) {
    if (!$('perspectives').children.length && !data.items.length) $('perspectives').append(text('p', 'Be the first to add a perspective. Contributions appear after staff review.'));
    data.items.forEach(row => {
      const e=card(row);
      if (row.parent_id) {e.classList.add('reply'); e.append(text('p','In reply to perspective ' + row.parent_id,'meta'));}
      if (state.profile && !state.profile.blocked && state.thread.open) e.append(button('Add a Reply', () => {
        state.parent=row.id; $('reply-context').textContent='Replying to ' + row.public_name + ': ' + row.body.slice(0,100);
        $('reply-context').hidden=false; $('clear-reply').hidden=false; $('perspective').focus();
      }));
      e.append(button('Report a Concern', async () => {
        const choices=['Privacy or confidential information','Harassment or threats','Spam or promotion','Misleading or unsafe content','Other concern'];
        const input=window.prompt('Concern type: 1 Privacy, 2 Harassment, 3 Spam, 4 Misleading or unsafe content, 5 Other. Enter 1–5.');
        if (!input) return;
        const reason=choices[Number(input)-1]; if (!reason) throw new Error('Choose a concern type from 1 to 5.');
        const detail=window.prompt('Optional context for the private staff review (up to 1,000 characters).') || '';
        await api('/perspectives/' + row.id + '/flags','POST',{reason,detail}); announce('Your concern was received for staff review.');
      }));
      $('perspectives').append(e);
    });
    state.perspectivesAfter=data.next || '';
    more('more-perspectives',data.next,async () => renderPerspectives(await api('/threads/' + state.thread.id + '?after=' + state.perspectivesAfter)));
  }
  async function mine(reset=false) {
    if (reset) {state.mineAfter=''; $('mine').replaceChildren();}
    const data=await api('/mine?after=' + state.mineAfter);
    if (reset && !data.items.length) $('mine').append(text('p','Your saved contributions will appear here, including those awaiting review.'));
    data.items.forEach(row => {
      const e=card(row); e.append(text('p','Status: ' + row.status + ' · Reference ' + row.id,'meta'));
      if (row.status !== 'Withdrawn') {
        e.append(button('Edit Your Perspective', () => {
          if (e.querySelector('form')) return;
          const form=document.createElement('form'); const label=text('label','Revise your perspective');
          const area=document.createElement('textarea'); area.id='edit-' + row.id; area.value=row.body; area.required=true; area.minLength=10; area.maxLength=4000; label.htmlFor=area.id;
          const save=text('button','Send the Revision for Review'); save.type='submit';
          form.append(label,area,save); e.append(form); area.focus();
          form.addEventListener('submit',ev => {ev.preventDefault(); action(async () => {
            await api('/perspectives/' + row.id,'PATCH',{version:row.version,body:area.value}); announce('Your revision is awaiting review.'); await mine(true); await threads(true); if(state.thread) await select(state.thread.id);
          });});
        }),button('Withdraw from Public View',async () => {
          if (!window.confirm('Remove this perspective and its reply branch from public view? Restricted review history remains.')) return;
          await api('/perspectives/' + row.id + '/withdraw','POST',{version:row.version}); announce('Your perspective has been withdrawn.'); await mine(true); await threads(true);
          if(state.thread) {try {await select(state.thread.id);} catch(e) {if(e.status!==404) throw e; $('conversation').hidden=true; state.thread=null; $('submit-perspective').disabled=true;}}
        }));
      }
      $('mine').append(e);
    });
    state.mineAfter=data.next || ''; more('more-mine',data.next,() => mine());
  }
  async function review(reset=false) {
    if (reset) {state.reviewAfter=''; $('review-queue').replaceChildren();}
    const data=await api('/review?after=' + state.reviewAfter);
    data.items.forEach(row => {
      const e=card(row); e.prepend(text('h3',row.title)); e.append(text('p',`${row.status} · Version ${row.version} · Reference ${row.id}`,'meta'));
      e.append(button('Review Version History',async () => {
        const history=await api('/history/' + row.id);
        const detail=document.createElement('details'); detail.open=true;detail.append(text('summary','Restricted version and review history'));
        history.revisions.forEach(r => detail.append(text('h3','Version ' + r.version),text('p',r.body,'body'),text('p','Hash: ' + r.content_hash,'meta')));
        history.events.forEach(r => detail.append(text('p',date(r.created_at) + ' · ' + r.action + ' · ' + r.detail,'body')));
        e.append(detail);
      }));
      if (row.status !== 'Withdrawn') {
        ['Approve','Hide','Reject'].forEach(command => e.append(button(command + ' This Version',async () => {
          const reason=window.prompt('Record a specific reason (at least 10 characters). Protect respectful disagreement.'); if(!reason) return;
          if(!window.confirm('Have you checked this exact version for privacy, permissions and publication suitability?')) return;
          await api('/review/' + row.id,'POST',{version:row.version,action:command,reason,privacy_and_rights_checked:true});
          announce('Review recorded.'); await review(true); await threads(true); await candidates(true);
        })));
        e.append(button('Pause Participant',async () => {
          const reason=window.prompt('Record why participation should be paused.'); if(!reason) return;
          await api('/participants/' + row.user_id + '/state','POST',{blocked:true,reason}); announce('Participation paused; existing publications require separate review.');
        }),button('Restore Participant',async () => {
          const reason=window.prompt('Record the participation restoration review.'); if(!reason) return;
          await api('/participants/' + row.user_id + '/state','POST',{blocked:false,reason}); announce('Participation restored.');
        }));
      }
      if(row.status==='Approved') e.append(button('Capture a Research Lead',async () => {
        const summary=window.prompt('Describe the research lead.'); if(!summary) return;
        const applicability=window.prompt('Where might it apply, and what must be investigated?'); if(!applicability) return;
        const restrictions=window.prompt('Record rights, privacy and reuse restrictions.'); if(!restrictions) return;
        await api('/perspectives/' + row.id + '/candidate','POST',{version:row.version,kind:'Research lead',summary,applicability,restrictions}); announce('Unvalidated candidate captured for separate research review.'); await candidates(true);
      }));
      $('review-queue').append(e);
    });
    state.reviewAfter=data.next || ''; more('more-review',data.next,() => review());
    $('flags').replaceChildren();
    if(!data.flags.length) $('flags').append(text('p','No open reported concerns.'));
    data.flags.forEach(row => {
      const e=text('article','','card'); e.append(text('h3',row.reason),text('p',row.detail,'body'),text('p','Perspective reference: ' + row.contribution_id,'meta'));
      e.append(button('Record Concern Disposition',async () => {
        const reason=window.prompt('Record the outcome. Hide or reject the contribution separately if action is required.'); if(!reason) return;
        const disposition=window.confirm('Was corrective action taken? Cancel records reviewed with no change.') ? 'Action taken' : 'Reviewed - no change';
        await api('/flags/' + row.id + '/disposition','POST',{disposition,reason}); announce('Concern review recorded.'); await review(true);
      })); $('flags').append(e);
    });
  }
  async function candidates(reset=false) {
    if(reset) {state.candidatesAfter=''; $('candidates').replaceChildren();}
    const data=await api('/candidates?after=' + state.candidatesAfter);
    if(reset && !data.items.length) $('candidates').append(text('p','No research candidates have been captured.'));
    data.items.forEach(row => {const e=text('article','','card'); e.append(text('h3',row.kind),text('p',row.summary,'body'),text('p',row.applicability),text('p','Restrictions: ' + row.restrictions),text('p',row.status + ' · Source ' + row.contribution_id + ' version ' + row.source_version,'meta')); $('candidates').append(e);});
    state.candidatesAfter=data.next || ''; more('more-candidates',data.next,() => candidates());
  }
  async function identity() {
    try {
      const data=await api('/me'); state.profile=data.participant; state.reviewer=data.reviewer;
      const accepted=Boolean(state.profile && state.profile.policy_version==='discovery-2026-10-03-v1');
      $('signin').hidden=true; $('profile-form').hidden=accepted;
      if(state.profile && !accepted) $('display-name').value=state.profile.display_name;
      $('participant-tools').hidden=!accepted;
      if(state.profile) {
        $('ask-question').href=state.profile.blocked ? '#contribute' : '#question-form';
        $('public-identity').textContent='Contributing as ' + state.profile.display_name + (state.profile.blocked ? '. Participation is paused; withdrawal remains available.' : '.');
        $('perspective-form').hidden=Boolean(state.profile.blocked); $('question-form').hidden=Boolean(state.profile.blocked); await mine(true);
      }
      $('staff').hidden=!state.reviewer; if(state.reviewer) {await review(true); await candidates(true);}
    } catch(e) {if(e.status !== 401) throw e;}
  }
  bind('profile-form',async () => {
    await api('/profile','POST',{display_name:$('display-name').value,consent:$('consent').checked,policy_version:'discovery-2026-10-03-v1'}); await identity(); announce('Your participation choice is saved.');
  });
  bind('perspective-form',async () => {
    if(!state.thread) throw new Error('Choose a conversation first.');
    const body=$('perspective').value; const fingerprint=JSON.stringify([state.thread.id,state.parent,body,$('prompt').value]);
    state.keys.perspective=state.keys.perspective?.fingerprint === fingerprint ? state.keys.perspective : {fingerprint,value:key()};
    await api('/threads/' + state.thread.id + '/perspectives','POST',{body,prompt:$('prompt').value,parent_id:state.parent,request_key:state.keys.perspective.value,website:$('website').value});
    $('perspective').value=''; state.keys.perspective=null; announce('Your perspective is saved for staff review. It is not public yet.'); await mine(true);
  });
  bind('question-form',async () => {
    const body=$('question-body').value,title=$('question-title').value; const fingerprint=JSON.stringify([title,body]);
    state.keys.question=state.keys.question?.fingerprint===fingerprint ? state.keys.question : {fingerprint,value:key()};
    await api('/questions','POST',{title,body,prompt:'What question should we be asking?',request_key:state.keys.question.value});
    $('question-form').reset(); state.keys.question=null; announce('Your Discovery Question is saved for review.'); await mine(true);
  });
  bind('insight-form',async () => {
    await api('/insights','POST',{insight_id:$('insight-id').value,title:$('insight-title').value,url:$('insight-url').value,source_version:$('insight-version').value,publication_review:$('insight-review').value});
    $('insight-form').reset(); announce('The reviewed Insight is connected.'); await threads(true);
  });
  $('clear-reply').onclick=() => {state.parent=null; $('reply-context').hidden=true; $('clear-reply').hidden=true; $('perspective').focus();};
  $('refresh-review').onclick=() => action(() => review(true));
  action(async () => {
    const policy=await api('/policy'); policy.prompts.forEach(p => {const option=text('option',p); option.value=p; $('prompt').append(option);});
    await threads(true); await identity();
    if(location.hash.startsWith('#conversation=')) await select(decodeURIComponent(location.hash.slice(14)));
  });
})();
