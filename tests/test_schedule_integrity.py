"""Behavioral regressions for schedules, imports, and saved team protection."""
from copy import deepcopy
from decimal import Decimal
from itertools import combinations, combinations_with_replacement
from pathlib import Path
import tempfile
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from app import Store, make_server
from engine import IDS, evaluate, final_lineups, final_schedule, new_state, validate
from test_tournament import fixture, cut_tie_state, final_tie_state


def exposure(matches, multiplier=1):
    roster=matches[0]['A']+matches[0]['B']
    return [sum((Decimal(str(multiplier)) if i<2 else 1)
                for i,m in enumerate(matches) if (p in m['A'])==(q in m['A']))
            for p,q in combinations(roster,2)]


class FinalSchedules(unittest.TestCase):
    def test_eight_games_cannot_have_equal_pair_exposure_even_with_repeats(self):
        # Exhaust all 24,310 multisets of eight games from the ten partitions.
        # This prevents claiming a mathematically impossible 3–4 range.
        roster=IDS[:6]
        teams=[{roster[0],*pair} for pair in combinations(roster[1:],2)]
        vectors=[[int((p in team)==(q in team)) for p,q in combinations(roster,2)] for team in teams]
        best=8
        for chosen in combinations_with_replacement(range(10),8):
            counts=[sum(vectors[i][j] for i in chosen) for j in range(15)]
            best=min(best,max(counts)-min(counts))
        self.assertEqual(best,2)

    def test_new_final_randomizes_slots_and_saves_optimized_schedule(self):
        s=fixture(False)
        with patch('engine.secrets.SystemRandom.shuffle',side_effect=lambda values:values.reverse()) as shuffle:
            final_lineups(s)
        self.assertTrue(shuffle.called)
        self.assertEqual(shuffle.call_args_list[0].args[0],list(reversed(s['final']['roster'])))
        original=deepcopy(s)
        matches=evaluate(s)['final']['schedule']
        self.assertEqual(len(matches),8)
        self.assertEqual(len({frozenset((frozenset(m['A']),frozenset(m['B']))) for m in matches}),8)
        for m in matches:
            self.assertEqual(len(m['A']),3)
            self.assertEqual(len(m['B']),3)
            self.assertEqual(sorted(m['A']+m['B']),sorted(s['final']['roster']))
        counts=exposure(matches)
        self.assertEqual((min(counts),max(counts)),(2,4))
        weighted=exposure(matches,2)
        self.assertEqual(max(weighted)-min(weighted),3)
        final_lineups(s)
        self.assertEqual(s,original)
        self.assertEqual(validate(s),s)

    def test_optimizer_respects_configured_multiplier(self):
        for multiplier in [0,.5,1,2,3,100000]:
            with self.subTest(multiplier=multiplier):
                s=fixture(False);s['settings']['multiplier']=multiplier
                final_lineups(s)
                matches=evaluate(s)['final']['schedule']
                def cost(games):
                    counts=exposure(games,multiplier)
                    return max(counts)-min(counts),sum(n*n for n in counts)
                alternatives=[]
                for first in combinations(range(8),2):
                    alternatives.append(cost([matches[i] for i in [*first,*[j for j in range(8) if j not in first]]]))
                self.assertEqual(cost(matches),min(alternatives))

    def test_scored_legacy_final_keeps_teams_scores_and_standings(self):
        for partial in [False,True]:
            s=fixture()
            if partial:
                for d in s['final']['players'].values():
                    d['goals'][1:]=[None]*7;d['results'][1:]=['']*7
            before=deepcopy(s);view=evaluate(s)
            s['final'].pop('lineups')
            s=validate(s);final_lineups(s)
            self.assertEqual(s['final']['players'],before['final']['players'])
            self.assertEqual(evaluate(s),view)

    def test_restarts_preserve_new_draw_and_reset_redraws(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json')
            store.save(fixture(False),restore=True,allow_draw=True)
            self.assertTrue(store.state['final']['lineups'])
            self.assertEqual(Store(store.path).state,store.state)
            before=deepcopy(store.state)
            cleared=deepcopy(before);cleared['final']=new_state()['final']
            store.save(cleared)
            self.assertTrue(store.state['final']['lineups'])
            self.assertEqual(store.state['round2'],before['round2'])
            store.save(before,restore=True,allow_draw=True)
            self.assertEqual(store.state,before)

    def test_malformed_lineups_are_rejected(self):
        s=fixture(False);final_lineups(s)
        bad_values=[None,{},[{}]*8,s['final']['lineups'][:7]]
        bad=deepcopy(s['final']['lineups']);bad[0]['A'][0]=bad[0]['B'][0];bad_values.append(bad)
        for bad in bad_values:
            with self.subTest(lineups=bad):
                edited=deepcopy(s);edited['final']['lineups']=bad
                with self.assertRaises(ValueError):validate(edited)

    def test_new_scores_and_limits_use_the_saved_teams(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json')
            store.save(fixture(False),restore=True,allow_draw=True)
            s=deepcopy(store.state)
            for i,m in enumerate(s['final']['lineups']):
                for team in ['A','B']:
                    for p in m[team]:
                        s['final']['players'][p]['goals'][i]=(2 if team=='A' else 1) if p==m[team][0] else 0
                        s['final']['players'][p]['results'][i]='W' if team=='A' else 'L'
            store.save(s)
            self.assertTrue(evaluate(store.state)['final']['ready'])
            self.assertEqual(Store(store.path).state,store.state)
            bad=deepcopy(store.state)
            for p in bad['final']['lineups'][0]['A'][:2]:bad['final']['players'][p]['goals'][0]=2
            with self.assertRaisesRegex(ValueError,'at most 3'):store.save(bad)


class SaveIntegrity(unittest.TestCase):
    def test_regular_save_cannot_replace_round1_or_final_teams(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json');store.save(fixture(),restore=True,allow_draw=True)
            before=deepcopy(store.state)
            for stage in ['round1','final']:
                edited=deepcopy(before)
                m=edited[stage]['lineups'][0]
                m['A'][0],m['B'][0]=m['B'][0],m['A'][0]
                with self.subTest(stage=stage),self.assertRaises(ValueError):store.save(edited)
                self.assertEqual(store.state,before)
                self.assertEqual(Store(store.path).state,before)
            edited=deepcopy(before);edited['final']['lineups']=[]
            with self.assertRaises(ValueError):store.save(edited)
            # Deliberate full resets are still supported and generate fresh R1 teams.
            cleared=new_state();cleared['names']=before['names']
            store.save(cleared)
            self.assertTrue(store.state['round1']['lineups'])
            self.assertEqual(store.state['final']['lineups'],[])

    def test_integral_json_floats_are_normalized_before_scoring(self):
        for s in [fixture(),cut_tie_state(),final_tie_state()]:
            for key in ['round1','round2','final']:
                for d in s[key]['players'].values():
                    d['goals']=[None if n is None else float(n) for n in d['goals']]
            s['round1']['extras']=[dict.fromkeys(IDS,0.0)]
            s['final']['extras']=[{p:{'goals':1.0 if p=='p1' else 0.0,'result':'W'} for p in IDS}]
            validated=validate(s)
            evaluate(validated)  # Used to fail with Fraction(float, int).
            self.assertIs(type(validated['round1']['players']['p1']['goals'][0]),int)
            self.assertIs(type(validated['round1']['extras'][0]['p1']),int)
            self.assertIs(type(validated['final']['extras'][0]['p1']['goals']),int)

    def test_huge_integer_is_validation_error(self):
        s=fixture();s['settings']['win_points']=10**1000
        with self.assertRaises(ValueError):validate(s)

    def test_version5_short_scores_migrate_before_lineup_indexing(self):
        s=fixture();s['version']=5;s['round2']['draw']['completed']=0
        for d in s['round2']['players'].values():d['goals']=d['goals'][:2]
        result=validate(s)
        for p in IDS:
            self.assertEqual(result['round2']['players'][p]['goals'],s['round2']['players'][p]['goals']+[None]*3)
        self.assertEqual(validate(result),result)

    def test_http_rejects_invalid_imports_and_lineup_edits_without_changing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'state.json');store.save(fixture(),restore=True,allow_draw=True)
            server=make_server(store,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            url=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(url+'/api/state') as response:info=json.load(response)
                headers={'Content-Type':'application/json','X-Session-Token':info['token']}
                candidates=[]
                for stage in ['round1','final']:
                    bad=deepcopy(store.state);m=bad[stage]['lineups'][0]
                    m['A'][0],m['B'][0]=m['B'][0],m['A'][0]
                    candidates.append(bad)
                bad=deepcopy(store.state);bad['settings']['multiplier']=10**1000;candidates.append(bad)
                for bad in candidates:
                    request=Request(url+'/api/state',data=json.dumps({'revision':info['revision'],'state':bad}).encode(),headers=headers,method='PUT')
                    with self.assertRaises(HTTPError) as caught:urlopen(request)
                    self.assertEqual(caught.exception.code,400);caught.exception.close()
                    with urlopen(url+'/api/state') as response:self.assertEqual(json.load(response),info)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_disconnect_during_response_is_ignored_but_other_io_errors_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=make_server(Store(Path(tmp)/'state.json'),0)
            try:
                handler=object.__new__(server.RequestHandlerClass)
                from unittest.mock import Mock
                handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock()
                handler.wfile=Mock()
                for failure in [BrokenPipeError,ConnectionResetError]:
                    handler.wfile.write.side_effect=failure
                    handler.send(200,{'ok':True})
                handler.wfile.write.side_effect=OSError('other failure')
                with self.assertRaises(OSError):handler.send(200,{'ok':True})
            finally:server.server_close()


if __name__=='__main__':unittest.main()
