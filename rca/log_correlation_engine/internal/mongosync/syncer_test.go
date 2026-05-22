package mongosync

import "testing"

func TestRuleSyncerNeedsSyncUsesIsSyncedGate(t *testing.T) {
	t.Run("missing state forces sync", func(t *testing.T) {
		syncer := &RuleSyncer{}
		if !syncer.needsSync(configState{}, false) {
			t.Fatal("expected missing state to force sync")
		}
	})

	t.Run("synced state skips sync", func(t *testing.T) {
		syncer := &RuleSyncer{}
		if syncer.needsSync(configState{Revision: 7, IsSynced: true}, true) {
			t.Fatal("expected synced state to skip sync")
		}
	})

	t.Run("pending state syncs once per revision locally", func(t *testing.T) {
		syncer := &RuleSyncer{}
		state := configState{Revision: 9, IsSynced: false}
		if !syncer.needsSync(state, true) {
			t.Fatal("expected pending state to sync when revision is unseen")
		}
		syncer.markSynced(state.Revision, true)
		if syncer.needsSync(state, true) {
			t.Fatal("expected same pending revision to be skipped after local sync")
		}
		if !syncer.needsSync(configState{Revision: 10, IsSynced: false}, true) {
			t.Fatal("expected a new pending revision to sync")
		}
	})

	t.Run("force full overrides synced state", func(t *testing.T) {
		syncer := &RuleSyncer{forceFull: true}
		if !syncer.needsSync(configState{Revision: 11, IsSynced: true}, true) {
			t.Fatal("expected force full to trigger sync")
		}
		if syncer.forceFull {
			t.Fatal("expected forceFull flag to be consumed")
		}
	})
}
