import type { EntityId, SystemRole } from '$lib/types/domain';

export interface User {
	id?: EntityId;
	username: string;
	role: SystemRole;
	encryptionReady?: boolean;
	encryptionNoticeAccepted?: boolean;
	docEncryptionKey?: string;
	avatarSeed?: string | null;
	avatarUrl?: string | null;
}

export interface CustomSession {
	user: User;
}

class UserState {
	session = $state<CustomSession | null>(null);

	avatarUrl = $derived(
		this.session?.user?.username
			? this.session.user.avatarUrl ||
				`https://api.dicebear.com/9.x/glass/svg?seed=${encodeURIComponent(this.session.user.avatarSeed || this.session.user.username)}`
			: null
	);

	setSession(newSession: CustomSession | null) {
		this.session = newSession;
		if (typeof window !== 'undefined') {
			if (newSession) {
				localStorage.setItem('amnesia_session', JSON.stringify(newSession));
			} else {
				localStorage.removeItem('amnesia_session');
			}
		}
	}

	loadFromLocalStorage() {
		if (typeof window !== 'undefined') {
			const saved = localStorage.getItem('amnesia_session');
			if (saved) {
				try {
					this.session = JSON.parse(saved);
				} catch {
					this.session = null;
				}
			}
		}
	}
}

export const userState = new UserState();
