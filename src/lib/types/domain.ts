export type EntityId = string | number;

export type SystemRole = 'root' | '管理员' | '用户';

export type TeamRole = 'owner' | 'admin' | 'member';

export type DocSpaceType = 'global' | 'team' | 'private';

export interface UserProfile {
	id: EntityId;
	username: string;
	systemRole: SystemRole;
	encryptionReady: boolean;
	encryptionNoticeAccepted?: boolean;
	createdAt?: string;
}

export interface TeamRecord {
	id: EntityId;
	name: string;
	slug: string;
	ownerUserId: EntityId;
	createdAt?: string;
}

export interface TeamMemberRecord {
	id: EntityId;
	teamId: EntityId;
	userId: EntityId;
	role: TeamRole;
	joinedAt?: string;
}

export interface TeamInviteRecord {
	id: EntityId;
	teamId: EntityId;
	token: string;
	role: TeamRole;
	createdByUserId: EntityId;
	expiresAt?: string | null;
	usedAt?: string | null;
	createdAt?: string;
}

export interface DocRecord {
	id: number;
	emoji: string;
	title: string;
	category: string;
	content: string;
	author?: string;
	created_at?: string;
	updated_at?: string;
	settings?: Record<string, unknown>;
	space_type?: DocSpaceType;
	owner_user_id?: EntityId | null;
	team_id?: EntityId | null;
	is_encrypted?: boolean;
	encryption_version?: number;
}

export interface RegisterPayload {
	username: string;
	password: string;
	inviteCode: string;
	systemRole?: SystemRole;
}

export interface LoginPayload {
	username: string;
	password: string;
}
