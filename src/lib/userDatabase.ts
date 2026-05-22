import { listSystemUsers, registerUserByAdmin, removeSystemUser } from '$lib/auth/authService';
import type { SystemRole, UserProfile } from '$lib/types/domain';

export interface UserRecord {
	id: string | number;
	username: string;
	role: SystemRole;
	encryptionReady?: boolean;
	createdAt?: string;
}

function toUserRecord(user: UserProfile): UserRecord {
	return {
		id: user.id,
		username: user.username,
		role: user.systemRole,
		encryptionReady: user.encryptionReady,
		createdAt: user.createdAt
	};
}

export async function getUsers(): Promise<UserRecord[]> {
	try {
		const users = await listSystemUsers();
		return users.map(toUserRecord);
	} catch (error: any) {
		console.error('getUsers error:', error?.message ?? error);
		return [];
	}
}

export async function addUser(user: {
	username: string;
	password: string;
	role: SystemRole;
}): Promise<{ success: boolean; message: string }> {
	try {
		const result = await registerUserByAdmin({
			username: user.username,
			password: user.password,
			systemRole: user.role
		});
		return result;
	} catch (error: any) {
		console.error('addUser error:', error?.message ?? error);
		return { success: false, message: '添加用户失败: ' + (error?.message ?? '未知错误') };
	}
}

export async function deleteUser(username: string): Promise<{ success: boolean; message: string }> {
	if (username === 'sout') {
		return { success: false, message: '系统限制：无法删除默认管理员' };
	}

	try {
		return await removeSystemUser(username);
	} catch (error: any) {
		console.error('deleteUser error:', error?.message ?? error);
		return { success: false, message: '删除用户失败: ' + (error?.message ?? '未知错误') };
	}
}
