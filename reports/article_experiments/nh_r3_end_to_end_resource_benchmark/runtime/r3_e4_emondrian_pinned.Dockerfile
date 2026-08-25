# STATIC TEMPLATE ONLY - DO NOT BUILD BEFORE R3-E MATERIALIZATION AUTHORIZATION.
FROM tomcat@sha256:81be7f8d435228148a6419d5e967e6c31f094ec3a492055b42c66d2bb775627c

COPY emondrian.war /tmp/emondrian.war

RUN rm -rf /usr/local/tomcat/webapps/emondrian \
    && mkdir -p /usr/local/tomcat/webapps/emondrian \
    && cd /usr/local/tomcat/webapps/emondrian \
    && jar -xf /tmp/emondrian.war \
    && rm -f /tmp/emondrian.war

COPY WEB-INF/ /usr/local/tomcat/webapps/emondrian/WEB-INF/
COPY mssql-jdbc-12.6.1.jre11.jar \
    /usr/local/tomcat/webapps/emondrian/WEB-INF/lib/mssql-jdbc-12.6.1.jre11.jar
