export interface User {
	username: string;
	role: 'root' | '管理员' | '用户';
}

export interface CustomSession {
	user: User;
}

class UserState {
	session = $state<CustomSession | null>(null);

	avatarUrl = $derived(
		this.session?.user?.username === 'sout'
			? 'https://api.dicebear.com/7.x/bottts/svg?seed=sout'
			: this.session?.user?.username
				? 'https://api.dicebear.com/7.x/bottts/svg?seed=' + this.session.user.username
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
