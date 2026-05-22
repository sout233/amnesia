import { supabase } from '$lib/supabaseClient';
import type { EntityId, TeamInviteRecord, TeamMemberRecord, TeamRecord, TeamRole } from '$lib/types/domain';

function normalizeTeam(row: Record<string, any>): TeamRecord {
	return {
		id: row.id,
		name: row.name,
		slug: row.slug,
		ownerUserId: row.owner_user_id,
		createdAt: row.created_at
	};
}

function normalizeTeamMember(row: Record<string, any>): TeamMemberRecord {
	return {
		id: row.id,
		teamId: row.team_id,
		userId: row.user_id,
		role: row.role,
		joinedAt: row.joined_at
	};
}

function normalizeTeamInvite(row: Record<string, any>): TeamInviteRecord {
	return {
		id: row.id,
		teamId: row.team_id,
		token: row.token,
		role: row.role ?? 'member',
		createdByUserId: row.created_by_user_id,
		expiresAt: row.expires_at,
		usedAt: row.used_at,
		createdAt: row.created_at
	};
}

export async function listUserTeams(userId: string) {
	const { data, error } = await supabase
		.from('amnesia_team_members')
		.select('id, team_id, user_id, role, joined_at, amnesia_teams(*)')
		.eq('user_id', userId);

	if (error) throw error;
	return ((data ?? []) as Array<Record<string, any>>).map((row) => ({
		...normalizeTeamMember(row),
		amnesia_teams: normalizeTeam(row.amnesia_teams ?? {})
	})) as Array<TeamMemberRecord & { amnesia_teams: TeamRecord }>;
}

export async function createTeam(input: { name: string; slug: string; ownerUserId: string }) {
	const { data, error } = await supabase
		.from('amnesia_teams')
		.insert({
			name: input.name,
			slug: input.slug,
			owner_user_id: input.ownerUserId
		})
		.select()
		.single();

	if (error) throw error;
	const team = normalizeTeam(data as Record<string, any>);

	const { error: memberError } = await supabase.from('amnesia_team_members').insert({
		team_id: team.id,
		user_id: input.ownerUserId,
		role: 'owner'
	});

	if (memberError) throw memberError;
	return team;
}

export async function createTeamInvite(input: {
	teamId: EntityId;
	createdByUserId: EntityId;
	role?: TeamRole;
	expiresAt?: string | null;
}) {
	const token =
		typeof crypto !== 'undefined' && 'randomUUID' in crypto
			? crypto.randomUUID()
			: `${Date.now()}-${Math.random().toString(36).slice(2)}`;

	const { data, error } = await supabase
		.from('amnesia_team_invites')
		.insert({
			team_id: input.teamId,
			token,
			role: input.role ?? 'member',
			created_by_user_id: input.createdByUserId,
			expires_at: input.expiresAt ?? null
		})
		.select()
		.single();

	if (error) throw error;
	return normalizeTeamInvite(data as Record<string, any>);
}

export async function listTeamInvites(teamId: EntityId) {
	const { data, error } = await supabase
		.from('amnesia_team_invites')
		.select('*')
		.eq('team_id', teamId)
		.order('created_at', { ascending: false });

	if (error) throw error;
	return ((data ?? []) as Array<Record<string, any>>).map(normalizeTeamInvite);
}

export async function acceptTeamInvite(token: string, userId: EntityId) {
	const nowIso = new Date().toISOString();
	const { data, error } = await supabase
		.from('amnesia_team_invites')
		.select('*')
		.eq('token', token)
		.is('used_at', null)
		.maybeSingle();

	if (error) throw error;
	if (!data) {
		return { success: false, message: '邀请链接不存在或已被使用' };
	}

	const invite = normalizeTeamInvite(data as Record<string, any>);
	if (invite.expiresAt && new Date(invite.expiresAt).getTime() < Date.now()) {
		return { success: false, message: '邀请链接已过期' };
	}

	const { error: memberError } = await supabase.from('amnesia_team_members').upsert(
		{
			team_id: invite.teamId,
			user_id: userId,
			role: invite.role ?? 'member'
		},
		{ onConflict: 'team_id,user_id' }
	);

	if (memberError) throw memberError;

	const { error: inviteUpdateError } = await supabase
		.from('amnesia_team_invites')
		.update({ used_at: nowIso })
		.eq('id', invite.id);

	if (inviteUpdateError) throw inviteUpdateError;
	return { success: true, message: '已加入团队', invite };
}
