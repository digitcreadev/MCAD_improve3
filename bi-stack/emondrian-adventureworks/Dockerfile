FROM tomcat:9.0-jdk17-temurin

ADD https://github.com/SergeiSemenkov/eMondrian/releases/latest/download/emondrian.war \
    /tmp/emondrian.war

RUN rm -rf /usr/local/tomcat/webapps/emondrian \
    && mkdir -p /usr/local/tomcat/webapps/emondrian \
    && cd /usr/local/tomcat/webapps/emondrian \
    && jar -xf /tmp/emondrian.war \
    && rm -f /tmp/emondrian.war

COPY WEB-INF/ /usr/local/tomcat/webapps/emondrian/WEB-INF/

ADD https://repo1.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/12.6.1.jre11/mssql-jdbc-12.6.1.jre11.jar \
    /usr/local/tomcat/webapps/emondrian/WEB-INF/lib/mssql-jdbc-12.6.1.jre11.jar
