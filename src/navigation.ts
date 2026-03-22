import { getPermalink, getBlogPermalink, getAsset } from './utils/permalinks';

export const headerData = {
  links: [
    {
      text: 'Trang Chủ',
      href: getPermalink('/'),
    },
    {
      text: 'Bài Viết',
      href: getBlogPermalink(),
    },
    {
      text: 'Về Ba Tê',
      href: getPermalink('/about'),
    },
  ],
  actions: [],
};

export const footerData = {
  links: [
    {
      title: 'Chủ Đề',
      links: [
        { text: 'Nguồn Gốc Cà Phê', href: getPermalink('/danh-muc/nguon-goc') },
        { text: 'Rang Xay', href: getPermalink('/danh-muc/rang-xay') },
        { text: 'Pha Chế', href: getPermalink('/danh-muc/pha-che') },
        { text: 'Nghiên Cứu', href: getPermalink('/danh-muc/nghien-cuu') },
      ],
    },
    {
      title: 'Blog',
      links: [
        { text: 'Tất Cả Bài Viết', href: getBlogPermalink() },
        { text: 'Về Ba Tê', href: getPermalink('/about') },
      ],
    },
  ],
  secondaryLinks: [
    { text: 'Điều Khoản', href: getPermalink('/terms') },
    { text: 'Chính Sách Bảo Mật', href: getPermalink('/privacy') },
  ],
  socialLinks: [{ ariaLabel: 'RSS', icon: 'tabler:rss', href: getAsset('/rss.xml') }],
  footNote: `
    ☕ <strong>Ba Tê và Cà Phê</strong> · Mọi quyền được bảo lưu.
  `,
};
