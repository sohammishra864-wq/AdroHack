import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, AuthSession } from '../lib/api';

export type UserRole = 'client' | 'reviewer';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarText: string;
  policyNumber?: string;
  title?: string;
  verified?: boolean;      // true = real Supabase login (token checked by the backend)
  appRole?: string;        // backend role from user_profiles: 'admin' | 'reviewer'
}

interface AuthContextType {
  user: UserProfile | null;
  role: UserRole | null;
  isAuthModalOpen: boolean;
  authModalInitialRole: UserRole;
  loginAsClient: (name?: string, email?: string) => void;
  loginAsReviewer: (name?: string) => void;
  authEnabled: boolean;    // backend has Supabase login switched on
  loginWithPassword: (email: string, password: string, role: UserRole) => Promise<void>;
  signupWithPassword: (name: string, email: string, password: string, role: UserRole) => Promise<string | null>;
  logout: () => void;
  openAuthModal: (role?: UserRole) => void;
  closeAuthModal: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalInitialRole, setAuthModalInitialRole] = useState<UserRole>('client');
  const [authEnabled, setAuthEnabled] = useState(false);

  useEffect(() => {
    api.authStatus().then((s) => setAuthEnabled(s.enabled));
  }, [isAuthModalOpen]);   // re-checked whenever the login dialog opens (mode may have changed)

  // Load persisted session
  useEffect(() => {
    try {
      const stored = localStorage.getItem('claimshield_session');
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch (e) {
      console.error('Failed to parse auth session', e);
    }
  }, []);

  const saveUserSession = (profile: UserProfile | null) => {
    setUser(profile);
    if (profile) {
      localStorage.setItem('claimshield_session', JSON.stringify(profile));
      if (profile.role === 'reviewer') {
        localStorage.setItem('claimshield_reviewer', profile.name.toLowerCase());
      }
    } else {
      localStorage.removeItem('claimshield_session');
    }
  };

  const loginAsClient = (name = 'Marcus Vance', email = 'marcus.vance@gmail.com') => {
    localStorage.removeItem('claimshield_token');
    const clientProfile: UserProfile = {
      id: 'client_01',
      name,
      email,
      role: 'client',
      avatarText: 'MV',
      policyNumber: 'POL-AUTO-948120',
      title: 'Policyholder',
    };
    saveUserSession(clientProfile);
    setIsAuthModalOpen(false);
  };

  const loginAsReviewer = (name = 'asha') => {
    localStorage.removeItem('claimshield_token');
    const reviewerProfile: UserProfile = {
      id: `rev_${name.toLowerCase()}`,
      name: name.charAt(0).toUpperCase() + name.slice(1),
      email: `${name.toLowerCase()}@claimshield.internal`,
      role: 'reviewer',
      avatarText: name.substring(0, 2).toUpperCase(),
      title: 'Senior Fraud Forensics Adjuster',
    };
    saveUserSession(reviewerProfile);
    setIsAuthModalOpen(false);
  };

  // Real login: the backend verifies the password with Supabase and returns a token
  const startSession = (s: AuthSession, role: UserRole) => {
    if (!s.access_token) return;
    localStorage.setItem('claimshield_token', s.access_token);
    const name = s.user.full_name || s.user.email.split('@')[0];
    saveUserSession({
      id: s.user.id,
      name,
      email: s.user.email,
      role,
      avatarText: name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase(),
      title: s.user.role === 'admin' ? 'Administrator' : role === 'client' ? 'Policyholder' : 'Fraud Forensics Adjuster',
      verified: true,
      appRole: s.user.role,
    });
    setIsAuthModalOpen(false);
  };

  const loginWithPassword = async (email: string, password: string, role: UserRole) => {
    startSession(await api.login(email, password), role);
  };

  // → null when logged straight in, else the backend's message (e.g. "confirm your email")
  const signupWithPassword = async (name: string, email: string, password: string, role: UserRole) => {
    const s = await api.signup(email, password, name);
    if (s.access_token) {
      startSession(s, role);
      return null;
    }
    return s.message || 'Account created. Please sign in.';
  };

  const logout = () => {
    api.logout().finally(() => localStorage.removeItem('claimshield_token'));
    saveUserSession(null);
  };

  const openAuthModal = (role: UserRole = 'client') => {
    setAuthModalInitialRole(role);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || null,
        isAuthModalOpen,
        authModalInitialRole,
        loginAsClient,
        loginAsReviewer,
        authEnabled,
        loginWithPassword,
        signupWithPassword,
        logout,
        openAuthModal,
        closeAuthModal,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
