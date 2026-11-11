FROM node:22-alpine AS dependencies
WORKDIR /workspace
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM dependencies AS build
COPY . .
RUN npm run build

FROM node:22-alpine AS production
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /workspace
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --from=build --chown=nextjs:nodejs /workspace/public ./public
COPY --from=build --chown=nextjs:nodejs /workspace/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /workspace/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

