var app_system_info = angular.module('systemInfo', []);
app_system_info.controller('factionList', function($scope, $http, $templateCache, $templateRequest, $rootScope) {
    $scope.tab_panel="";
    $scope.submit = function() {
      $http.post("system_factions",$scope.star_system)
        .then(function (response) {
          $scope.factions = response.data;
          $scope.system = $scope.star_system;
        });
      $http.post("near_systems",$scope.star_system)
      .then(function (response) {
        $scope.systems = response.data;
      });
      $http.post("next_expansion",$scope.star_system)
      .then(function (response) {
        $scope.next_expansion = response.data;
        console.log($scope.next_expansion);
      });
    };
});
app_system_info.directive("factionSystemList", function() {
    return {
        restrict : "E",
        templateUrl : "faction_system_list"
    };
});

app_system_info.directive("nearSystemsList", function() {
    return {
        restrict : "E",
        templateUrl : "near_systems_list"
    };
});